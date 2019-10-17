
import json
import time
import os
import re
import socket
import pprint
import logging
from os.path import join
from os.path import exists

import utils as global_utils
from . import utils
from .models import model_config

from .dataset.readers import readers_config

import numpy as np
import torch



class Evaluator:
  """Evaluate a Pytorch Model."""

  def __init__(self, params):


    # Set up environment variables before doing any other global initialization to
    # make sure it uses the appropriate environment variables.
    utils.set_default_param_values_and_env_vars(params)

    self.params = params

    # Setup logging & log the version.
    global_utils.setup_logging(params.logging_verbosity)
    logging.info("Pytorch version: {}.".format(torch.__version__))
    logging.info("Hostname: {}.".format(socket.gethostname()))

    # print self.params parameters
    pp = pprint.PrettyPrinter(indent=2, compact=True)
    logging.info(pp.pformat(params.values()))

    self.train_dir = self.params.train_dir
    self.logs_dir = "{}_logs".format(self.train_dir)
    if self.train_dir is None:
      raise ValueError('Trained model directory not specified')
    self.num_gpus = self.params.num_gpus

    # create a mesage builder for logging
    self.message = global_utils.MessageBuilder()

    if self.params.num_gpus:
      self.batch_size = self.params.batch_size * self.num_gpus
    else:
      self.batch_size = self.params.batch_size

    if not self.params.data_pattern:
      raise IOError("'data_pattern' was not specified. "
        "Nothing to evaluate.")

    # load reader and model
    self.reader = readers_config[self.params.dataset](
      self.params, self.batch_size, self.num_gpus, is_training=False)
    self.model = model_config.get_model_config(
        self.params.model, self.params.dataset, self.params,
        self.reader.n_classes, is_training=False)
    # TODO: get the loss another way
    self.criterion = torch.nn.CrossEntropyLoss().cuda()
    # we don't use DataParallel with 1 gpu due to bug with fft
    if self.num_gpus > 1:
      self.model = torch.nn.DataParallel(self.model)
    self.model = self.model.cuda()


  def run(self):
    """Evaluate a model every self.params.eval_interval_secs.

    Returns:
      Dictionary containing eval statistics. Currently returns an empty
      dictionary.

    Raises:
      ValueError: If self.params.train_dir is unspecified.
    """
    logging.info("Building evaluation graph")

    # those variables are updated in eval_loop
    self.best_global_step = None
    self.best_accuracy = None
    # if the evaluation is made during training, we don't know how many 
    # checkpoint we need to process
    if self.params.eval_during_training:
      last_global_step = 0
      while True:
        latest_checkpoint, global_step = global_utils.get_checkpoint(
          self.train_dir, last_global_step, backend='pytorch')
        if latest_checkpoint is None or global_step == last_global_step:
          time.sleep(self.params.eval_interval_secs)
          continue
        else:
          logging.info(
            "Loading checkpoint for eval: {}".format(latest_checkpoint))
          # Restores from checkpoint
          checkpoint = torch.load(ckpt)
          global_step = checkpoint['global_step']
          epoch = checkpoint['epoch']
          self.model.load_state_dict(checkpoint['model_state_dict'])
          self.model.eval()
          self.eval_loop(global_step, epoch)
          last_global_step = global_step
    # if the evaluation is made after training, we look for all
    # checkpoints 
    else:
      ckpts = global_utils.get_list_checkpoints(
        self.train_dir, backend='pytorch')
      # remove first checkpoint model.ckpt-0
      ckpts.pop(0)
      for ckpt in ckpts:
        logging.info(
          "Loading checkpoint for eval: {}".format(ckpt))
        # Restores from checkpoint
        checkpoint = torch.load(ckpt)
        global_step = checkpoint['global_step']
        epoch = checkpoint['epoch']
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        self.eval_loop(global_step, epoch)

    path = join(self.logs_dir, "best_accuracy.txt")
    with open(path, 'w') as f:
      f.write("{}\t{:.4f}\n".format(
        self.best_global_step, self.best_accuracy))

    logging.info("Done evaluation -- number of eval reached.")


  def eval_loop(self, global_step, epoch):
    """Run the evaluation loop once."""

    running_accuracy = 0
    running_inputs = 0
    running_loss = 0
    for batch_n, data in enumerate(self.reader.load_dataset()):

      with torch.no_grad():
        batch_start_time = time.time()
        inputs, labels = data
        inputs, labels = inputs.cuda(), labels.cuda()
        outputs = self.model(inputs)
        loss = self.criterion(outputs, labels)
        _, predicted = torch.max(outputs.data, 1)
        seconds_per_batch = time.time() - batch_start_time
        examples_per_second = inputs.size(0) / seconds_per_batch

      running_accuracy += predicted.eq(labels.data).cpu().sum().numpy()
      running_inputs += inputs.size(0)
      running_loss += loss.cpu().numpy()
      accuracy = running_accuracy / running_inputs
      loss = running_loss / (batch_n + 1)

      self.message.add('step', global_step)
      self.message.add('accuracy', accuracy, format='.5f')
      self.message.add('loss', loss, format='.5f')
      self.message.add('imgs/sec', examples_per_second, format='.0f')
      logging.info(self.message.get_message())

    if self.best_accuracy is None or self.best_accuracy < accuracy:
      self.best_global_step = global_step
      self.best_accuracy = accuracy
    self.message.add('step', global_step)
    self.message.add('accuracy', accuracy, format='.5f')
    self.message.add('loss', loss, format='.5f')
    logging.info(self.message.get_message())
    logging.info("Done with batched inference.")
    return
