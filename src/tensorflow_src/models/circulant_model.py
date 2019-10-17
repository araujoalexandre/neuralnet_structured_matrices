
import logging

import numpy as np
import tensorflow as tf

from . import model as model_lib


class DiagonalCirculantModel(model_lib.CNNModel):

  def __init__(self, params):
    self.model_params = params.model_params
    super(DiagonalCirculantModel, self).__init__(
        'DiagonalCirculantModel', params=params)

  def skip_final_affine_layer(self):
    return True

  def add_inference(self, cnn):
    n_layers = self.model_params['n_layers']
    cnn.top_layer = tf.layers.flatten(cnn.top_layer)
    cnn.top_size = cnn.top_layer.get_shape()[-1].value
    for i in range(n_layers):
      cnn.diagonal_circulant(**self.model_params)
    cnn.diagonal_circulant(num_channels_out=cnn.nclass,
                          activation='linear')


class ConvCirculant(model_lib.CNNModel):

  def __init__(self, params):
    assert params.data_format == 'NCHW'
    self.model_params = params.model_params
    super(ConvCirculant, self).__init__(
      'ConvCirculant', params=params)

  def skip_final_affine_layer(self):
    return False

  def _bottleneck(self, cnn, channel, strides=1, residual=True):
    if residual:
      x = cnn.top_layer
    cnn.conv(channel, 1, 1)
    cnn.depth_conv_circ(**self.model_params)
    if strides > 1:
      cnn.mpool(strides, strides)
    cnn.conv(channel, 1, 1, activation='linear')
    if residual and strides == 1:
      cnn.top_layer = cnn.top_layer + x
    logging.info('shape {}'.format(cnn.top_layer.get_shape()))

  def add_inference(self, cnn):

    self._bottleneck(cnn, 32, strides=1, residual=False)

    self._bottleneck(cnn, 16, strides=1, residual=False)
    self._bottleneck(cnn, 16, strides=1)

    self._bottleneck(cnn, 24, strides=2)
    self._bottleneck(cnn, 24, strides=1)
    self._bottleneck(cnn, 24, strides=1)

    self._bottleneck(cnn, 32, strides=2)
    self._bottleneck(cnn, 32, strides=1)
    self._bottleneck(cnn, 32, strides=1)

    self._bottleneck(cnn, 64, strides=2)
    self._bottleneck(cnn, 64, strides=1)
    self._bottleneck(cnn, 64, strides=1)

    self._bottleneck(cnn, 96, strides=1, residual=False)
    self._bottleneck(cnn, 96, strides=1)
    self._bottleneck(cnn, 96, strides=1)

    cnn.flatten()



class ConvDiagonalCirculantModel(model_lib.CNNModel):

  def __init__(self, params):
    self.model_params = params.model_params
    super(ConvDiagonalCirculantModel, self).__init__(
        'ConvDiagonalCirculantModel', params=params)

  def skip_final_affine_layer(self):
    return True

  def add_inference(self, cnn):
    n_layers = self.model_params['n_layers']
    trainable = self.model_params['trainable']
    n_channels = self.model_params['n_channels']
    if type(n_channels) == str:
      n_channels = list(map(int, n_channels.split('/')))
    elif type(n_channels) == int:
      n_channels = [n_channels]
    else:
      raise ValueError("n_channels type not recognized")

    for channel in n_channels:
      cnn.conv(channel, 3, 3, 1, 1, mode='SAME', trainable=trainable)
      cnn.mpool(2, 2, 2, 2, mode='VALID')

    cnn.top_layer = tf.layers.flatten(cnn.top_layer)
    cnn.top_size = cnn.top_layer.get_shape()[-1].value
    for i in range(n_layers):
      cnn.diagonal_circulant(**self.model_params)
    cnn.diagonal_circulant(num_channels_out=cnn.nclass,
                          activation='linear')



class DiagonalCirculantByChannel(model_lib.CNNModel):

  def __init__(self, params):
    self.model_params = params.model_params
    super(DiagonalCirculantByChannel, self).__init__(
      'DiagonalCirculantByChannel', params=params)

  def skip_final_affine_layer(self):
    return True

  def add_channel_inference(self, cnn, params_channel):
    for _ in range(params_channel['n_layers']):
      cnn.flatten()
      cnn.diagonal_circulant(**params_channel)
      cnn.reshape((-1, 1, 32, 32))
      cnn.batch_norm()
    cnn.flatten()
    return cnn.top_layer

  def add_inference(self, cnn):

    params_channel = self.model_params['channels']
    params_classification = self.model_params['classification']

    x = cnn.top_layer
    x1, x2, x3 = tf.unstack(x, axis=1)

    cnn.top_layer = x1
    x1 = self.add_channel_inference(cnn, params_channel)
    cnn.top_layer = x2
    x2 = self.add_channel_inference(cnn, params_channel)
    cnn.top_layer = x3
    x3 = self.add_channel_inference(cnn, params_channel)

    x = tf.reduce_mean([x1, x2, x3], 0)

    cnn.top_layer = x
    cnn.top_size = x.get_shape()[-1].value
    for i in range(params_classification['n_layers']):
      cnn.diagonal_circulant(**params_classification)
    cnn.diagonal_circulant(num_channels_out=cnn.nclass,
                          activation='linear')


