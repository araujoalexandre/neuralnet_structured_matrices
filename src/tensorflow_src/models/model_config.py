# Copyright 2017 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

"""Model configurations for CNN benchmarks.
"""

from functools import partial

from . import alexnet_model
from . import densenet_model
from . import googlenet_model
from . import inception_model
from . import lenet_model
from . import mobilenet_v2
from . import nasnet_model
from . import official_resnet_model
from . import overfeat_model
from . import resnet_model
from . import ssd_model
from . import trivial_model
from . import vgg_model
from . import wide_resnet_model
from . import circulant_model
from . import distillation_model
from . import scattering_model

from .experimental import deepspeech
from .experimental import official_ncf_model


_model_name_to_imagenet_model = {
    'vgg11': vgg_model.Vgg11Model,
    'vgg16': vgg_model.Vgg16Model,
    'vgg19': vgg_model.Vgg19Model,
    'lenet': lenet_model.Lenet5Model,
    'googlenet': googlenet_model.GooglenetModel,
    'overfeat': overfeat_model.OverfeatModel,
    'alexnet': alexnet_model.AlexnetModel,
    'trivial': trivial_model.TrivialModel,
    'inception3': inception_model.Inceptionv3Model,
    'inception4': inception_model.Inceptionv4Model,
    'official_resnet18_v2':
        partial(official_resnet_model.ImagenetResnetModel, 18),
    'official_resnet34_v2':
        partial(official_resnet_model.ImagenetResnetModel, 34),
    'official_resnet50_v2':
        partial(official_resnet_model.ImagenetResnetModel, 50),
    'official_resnet101_v2':
        partial(official_resnet_model.ImagenetResnetModel, 101),
    'official_resnet152_v2':
        partial(official_resnet_model.ImagenetResnetModel, 152),
    'official_resnet200_v2':
        partial(official_resnet_model.ImagenetResnetModel, 200),
    'official_resnet18':
        partial(official_resnet_model.ImagenetResnetModel, 18, version=1),
    'official_resnet34':
        partial(official_resnet_model.ImagenetResnetModel, 34, version=1),
    'official_resnet50':
        partial(official_resnet_model.ImagenetResnetModel, 50, version=1),
    'official_resnet101':
        partial(official_resnet_model.ImagenetResnetModel, 101, version=1),
    'official_resnet152':
        partial(official_resnet_model.ImagenetResnetModel, 152, version=1),
    'official_resnet200':
        partial(official_resnet_model.ImagenetResnetModel, 200, version=1),
    'resnet50': resnet_model.create_resnet50_model,
    'resnet50_v1.5': resnet_model.create_resnet50_v1_5_model,
    'resnet50_v2': resnet_model.create_resnet50_v2_model,
    'resnet101': resnet_model.create_resnet101_model,
    'resnet101_v2': resnet_model.create_resnet101_v2_model,
    'resnet152': resnet_model.create_resnet152_model,
    'resnet152_v2': resnet_model.create_resnet152_v2_model,
    'nasnet': nasnet_model.NasnetModel,
    'nasnetlarge': nasnet_model.NasnetLargeModel,
    'mobilenet': mobilenet_v2.MobilenetModel,
    'ncf': official_ncf_model.NcfModel,
}


_model_name_to_cifar_model = {
    'trivial': trivial_model.TrivialModel,
    'conv_dense': trivial_model.ConvDenseModel,
    'lenet': lenet_model.Lenet5Model,
    'alexnet': alexnet_model.AlexnetCifar10Model,
    'resnet20': resnet_model.create_resnet20_cifar_model,
    'resnet20_v2': resnet_model.create_resnet20_v2_cifar_model,
    'resnet32': resnet_model.create_resnet32_cifar_model,
    'resnet32_v2': resnet_model.create_resnet32_v2_cifar_model,
    'resnet44': resnet_model.create_resnet44_cifar_model,
    'resnet44_v2': resnet_model.create_resnet44_v2_cifar_model,
    'resnet56': resnet_model.create_resnet56_cifar_model,
    'resnet56_v2': resnet_model.create_resnet56_v2_cifar_model,
    'resnet110': resnet_model.create_resnet110_cifar_model,
    'resnet110_v2': resnet_model.create_resnet110_v2_cifar_model,
    'densenet40_k12': densenet_model.create_densenet40_k12_model,
    'densenet100_k12': densenet_model.create_densenet100_k12_model,
    'densenet100_k24': densenet_model.create_densenet100_k24_model,
    'nasnet': nasnet_model.NasnetCifarModel,

    'wide_resnet': wide_resnet_model.WideResnetModel,
    'diagonal_circulant': circulant_model.DiagonalCirculantModel,
    'distillation_resnet56_v2_circulant':
      distillation_model.create_distillation_resnet56_v2_circulant,
    'scattering_circulant': scattering_model.ScatteringHybridCirculantModel,
    'scattering_dense': scattering_model.ScatteringHybridDenseModel,
    'conv_circulant': circulant_model.ConvCirculant,
    'conv_diagonal_circulant': circulant_model.ConvDiagonalCirculantModel,
    'random_diagonal_circulant': circulant_model.RandomDiagCirculantModel,
    'random_resnet_diagonal_circulant':
      circulant_model.RandomResnetDiagCirculantModel,
    'diagonal_circulant_by_channel': circulant_model.DiagonalCirculantByChannel
}

_model_name_to_object_detection_model = {
    'trivial': trivial_model.TrivialSSD300Model,
    'ssd300': ssd_model.SSD300Model,
}

_model_name_to_mnist_model = {
  'trivial': trivial_model.TrivialModel,
  'lenet': lenet_model.Lenet5Model,
  'diagonal_circulant': circulant_model.DiagonalCirculantModel
}

def _get_model_map(dataset_name):
  """Get name to model map for specified dataset."""
  if dataset_name in ('cifar10', 'cifar100'):
    return _model_name_to_cifar_model
  elif dataset_name == 'mnist':
    return _model_name_to_mnist_model
  elif dataset_name in ('imagenet', 'synthetic'):
    return _model_name_to_imagenet_model
  elif dataset_name == 'librispeech':
    return {'deepspeech2': deepspeech.DeepSpeech2Model}
  elif dataset_name == 'coco':
    return _model_name_to_object_detection_model
  else:
    raise ValueError('Invalid dataset name: %s' % dataset_name)


def get_model_config(model_name, dataset_name, params):
  """Map model name to model network configuration."""
  model_map = _get_model_map(dataset_name)
  if model_name not in model_map:
    raise ValueError('Invalid model name \'%s\' for dataset \'%s\'' %
                     (model_name, dataset_name))
  else:
    return model_map[model_name](params=params)


def register_model(model_name, dataset_name, model_func):
  """Register a new model that can be obtained with `get_model_config`."""
  model_map = _get_model_map(dataset_name)
  if model_name in model_map:
    raise ValueError('Model "%s" is already registered for dataset "%s"' %
                     (model_name, dataset_name))
  model_map[model_name] = model_func
