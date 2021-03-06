
import os
import time
import datetime
import pprint
import socket
import logging
import warnings
from os import mkdir
from os.path import join
from os.path import exists

import utils as global_utils
from . import utils
from .models import model_config

from .dataset.readers import readers_config

import numpy as np
import torch
import torch.nn.functional as F
import torch.backends.cudnn as cudnn
import torch.distributed as dist
from torch.optim import lr_scheduler
from torch.nn.parallel import DistributedDataParallel


def get_scheduler(optimizer, lr_scheduler, lr_scheduler_params):
  """Return a learning rate scheduler
  schedulers. See https://pytorch.org/docs/stable/optim.html for more details.
  """
  if lr_scheduler == 'piecewise_constant':
    raise NotImplementedError
  elif lr_scheduler == 'step_lr':
    scheduler = torch.optim.lr_scheduler.StepLR(
        optimizer, **lr_scheduler_params)
  elif lr_scheduler == 'multi_step_lr':
    scheduler = torch.optim.lr_scheduler.MultiStepLR(
      optimizer, **lr_scheduler_params)
  elif lr_scheduler == 'exponential_lr':
    scheduler = torch.optim.lr_scheduler.ExponentialLR(
      optimizer, **lr_scheduler_params)
  elif lr_scheduler == 'reduce_lr_on_plateau':
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
      optimizer, **lr_scheduler_params)
  elif lr_scheduler == 'cyclic_lr':
    scheduler = torch.optim.lr_scheduler.CyclicLR(
      optimizer, **lr_scheduler_params)
  else:
    raise ValueError("scheduler was not recognized")
  return scheduler


def get_optimizer(optimizer, opt_args, init_lr, weight_decay, params):
  """Returns the optimizer that should be used based on params."""
  if optimizer == 'sgd':
    opt = torch.optim.SGD(
      params, lr=init_lr, weight_decay=weight_decay, **opt_args)
  elif optimizer == 'rmsprop':
    opt = torch.optim.RMSprop(
      params, lr=init_lr, weight_decay=weight_decay, **opt_args)
  elif optimizer == 'adam':
    opt = torch.optim.Adam(
      params, lr=init_lr, weight_decay=weight_decay, **opt_args)
  else:
    raise ValueError("Optimizer was not recognized")
  return opt


class Trainer:
  """A Trainer to train a PyTorch."""

  def __init__(self, params):
    """Creates a Trainer.
    """
    utils.set_default_param_values_and_env_vars(params)
    self.params = params

    # Setup logging & log the version.
    global_utils.setup_logging(params.logging_verbosity)
    logging.info("PyTorch version: {}.".format(torch.__version__))
    logging.info("Hostname: {}.".format(socket.gethostname()))

    # print self.params parameters
    pp = pprint.PrettyPrinter(indent=2, compact=True)
    logging.info(pp.pformat(params.values()))

    self.job_name = self.params.job_name  # "" for local training
    self.is_distributed = bool(self.job_name)
    self.task_index = self.params.task_index
    self.local_rank = self.params.local_rank
    self.start_new_model = self.params.start_new_model
    self.train_dir = self.params.train_dir
    self.num_gpus = self.params.num_gpus
    if self.num_gpus and not self.is_distributed:
      self.batch_size = self.params.batch_size * self.num_gpus
    else:
      self.batch_size = self.params.batch_size

    if self.is_distributed:
      self.num_nodes = len(params.worker_hosts.split(';'))
      self.world_size = self.num_nodes * self.num_gpus
      self.rank = self.task_index * self.num_gpus + self.local_rank
      dist.init_process_group(
        backend='nccl', init_method='env://',
        timeout=datetime.timedelta(seconds=30))
      if self.local_rank == 0:
        logging.info('world size={}'.format(self.world_size))
      logging.info('Distributed init done, local_rank={}, rank={}'.format(
        self.local_rank, self.rank))
      self.is_master = bool(self.rank == 0)
    else:
      self.is_master = True

    # create a mesage builder for logging
    self.message = global_utils.MessageBuilder()

    # load reader and model
    self.reader = readers_config[self.params.dataset](
      self.params, self.batch_size, self.num_gpus, is_training=True)
    self.model = model_config.get_model_config(
        self.params.model, self.params.dataset, self.params,
        self.reader.n_classes, is_training=True)
    if not params.job_name:
      self.model = torch.nn.DataParallel(self.model)
      self.model = self.model.cuda()
    else:
      torch.cuda.set_device(params.local_rank)
      self.model = self.model.cuda()
      i = params.local_rank
      self.model = DistributedDataParallel(
        self.model, device_ids=[i], output_device=i)
      logging.info('model defined with DistributedDataParallel')

    # if adversarial training, create the attack class
    if self.params.adversarial_training:
      attack_params = self.params.adversarial_training_params

      # from advertorch import attacks
      # self.adversaries = {}
      # self.adversaries["PGDLinf"] = attacks.LinfPGDAttack(
      #   self.model, eps=0.031, nb_iter=10, eps_iter=2*0.031/10,
      #   rand_init=True, clip_min=0.0, clip_max=1.0)
      #
      # self.adversaries["PGDL2"] = attacks.L2PGDAttack(
      #   self.model, eps=0.83, nb_iter=10, eps_iter=2*0.83/10,
      #   rand_init=True, clip_min=0.0, clip_max=1.0)

      self.attack = utils.get_attack(
                      self.model,
                      self.reader.n_classes,
                      self.params.adversarial_training_name,
                      attack_params)

  def run(self):
    """Performs training on the currently defined Tensorflow graph.
    """
    # reset the training directory if start_new_model is True
    if self.is_master and self.start_new_model and exists(self.train_dir):
      global_utils.remove_training_directory(self.train_dir)
    if self.is_master:
      mkdir(self.train_dir)

    if self.params.torch_random_seed is not None:
      random.seed(self.params.torch_random_seed)
      torch.manual_seed(self.params.torch_random_seed)
      cudnn.deterministic = True
      warnings.warn('You have chosen to seed training. '
                    'This will turn on the CUDNN deterministic setting, '
                    'which can slow down your training considerably! '
                    'You may see unexpected behavior when restarting '
                    'from checkpoints.')

    if self.params.cudnn_benchmark:
      cudnn.benchmark = True

    # save the parameters in json formet in the training directory
    model_flags_dict = self.params.to_json()
    log_folder = '{}_logs'.format(self.train_dir)
    flags_json_path = join(log_folder, "model_flags.json")
    if not exists(flags_json_path):
      with open(flags_json_path, "w") as fout:
        fout.write(model_flags_dict)

    self._run_training()


  def _run_training(self):

    self.criterion = torch.nn.CrossEntropyLoss().cuda()
    self.optimizer = get_optimizer(
                       self.params.optimizer,
                       self.params.optimizer_params,
                       self.params.init_learning_rate,
                       self.params.weight_decay,
                       self.model.parameters())

    scheduler = get_scheduler(
      self.optimizer, self.params.lr_scheduler,
      self.params.lr_scheduler_params)

    global_step = 0
    data_loader, sampler = self.reader.load_dataset()

    batch_size = self.batch_size
    if self.is_distributed:
      n_files = sampler.num_samples
    else:
      n_files = self.reader.n_train_files

    if self.local_rank == 0:
      logging.info("Start training")
      if self.params.adversarial_training:
        logging.info("Using Adv strategy: {}".format(
          self.params.adv_strategy))
    for i in range(self.params.num_epochs):
      if self.is_distributed:
        sampler.set_epoch(i)
      for data in data_loader:
        epoch = (int(global_step) * batch_size) / n_files
        self._training(data, epoch, global_step)
        self.save_ckpt(global_step, epoch)
        global_step += 1
      scheduler.step()
    self.save_ckpt(global_step, epoch, final=True)
    logging.info("Done training -- epoch limit reached.")

  def save_ckpt(self, step, epoch, final=False):
    """Save ckpt in train directory."""
    if (epoch % self.params.save_checkpoint_epochs == 0
         and self.is_master) or (final and self.is_master):
      state = {
        'epoch': epoch,
        'global_step': step,
        'model_state_dict': self.model.state_dict(),
        'optimizer_state_dict': self.optimizer.state_dict(),
      }
      ckpt_name = "model.ckpt-{}.pth".format(step)
      logging.info("Saving checkpoint '{}'.".format(ckpt_name))
      torch.save(state, join(self.train_dir, ckpt_name))


  def _training(self, data, epoch, step):

    batch_start_time = time.time()
    inputs, labels = data
    inputs = inputs.cuda(non_blocking=True)
    labels = labels.cuda(non_blocking=True)

    if self.params.adversarial_training:

      if self.params.adv_strategy == "single":
        inputs = self.attack.perturb(inputs, labels)

      if self.params.adv_strategy == "mean":

        loss = 0
        for att in self.adversaries.keys():
          inputs_adv = self.adversaries[att].perturb(inputs, labels)
          outputs = self.model(inputs_adv)
          loss += self.criterion(outputs, labels)
        loss /= len(self.adversaries.keys())
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

      elif self.params.adv_strategy == "rand":
        att = random.choice(list(self.adversaries.keys()))
        inputs_adv = self.adversaries[att].perturb(inputs, labels)
        outputs = self.model(inputs_adv)
        loss = self.criterion(outputs, labels)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

      elif self.params.adv_strategy == "max":
        loss = torch.zeros_like(labels).float()
        for att in self.adversaries.keys():
          inputs_adv = self.adversaries[att].perturb(inputs, labels)
          outputs = self.model(inputs_adv)
          l = self.criterion(outputs, labels).float()
          loss = torch.max(loss, l)
        loss = loss.mean()
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

    else:
      
      outputs = self.model(inputs)
      self.optimizer.zero_grad()
      loss = self.criterion(outputs, labels.cuda())
      loss.backward()

      if self.params.gradient_clip_by_norm:
        torch.nn.utils.clip_grad_norm_(
          self.model.parameters(), self.params.gradient_clip_by_norm)
      elif self.params.gradient_clip_by_value:
        torch.nn.utils.clip_grad_value_(
          self.model.parameters(), self.params.gradient_clip_by_value)
      
      self.optimizer.step()
    
    seconds_per_batch = time.time() - batch_start_time
    examples_per_second = self.batch_size / seconds_per_batch

    local_rank = self.local_rank
    to_print = step % self.params.frequency_log_steps == 0
    if (to_print and local_rank == 0) or (step == 1 and local_rank == 0):
      lr = self.optimizer.param_groups[0]['lr']
      self.message.add("epoch", epoch, format="4.2f")
      self.message.add("step", step, width=5, format=".0f")
      self.message.add("lr", lr, format=".6f")
      self.message.add("loss", loss, format=".4f")
      self.message.add("imgs/sec", examples_per_second, width=5, format=".0f")
      logging.info(self.message.get_message())


