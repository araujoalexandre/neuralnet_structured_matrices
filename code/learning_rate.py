
import tensorflow as tf
from tensorflow import flags
from tensorflow import logging
from tensorflow.python.eager import context
from tensorflow.python.framework import ops
from tensorflow.python.ops import math_ops


FLAGS = flags.FLAGS

# global
flags.DEFINE_string("learning_rate_strategy", "exponential_decay",
                    "Learning rate strategy to use for training. Choices are "
                    "['exponential_decay', 'cyclic_learning_rate'].")

# Piecewise constant
flags.DEFINE_string("boundaries", "4,8,12,16,20,24",
                    "A list of Tensors or ints or floats with strictly"
                    " increasing entries")
flags.DEFINE_string("values", "1e-1,2e-2,4e-3,8e-4,1.6e-4,3.2e-5,6.4e-6",
                    "A list of Tensors or floats or ints that specifies the "
                    "values for the intervals defined by boundaries")

# Exponential decay
flags.DEFINE_float("base_learning_rate", 0.01,
                   "Which learning rate to start with.")
flags.DEFINE_float("learning_rate_decay", 0.95,
                   "Learning rate decay factor to be applied every "
                   "learning_rate_decay_examples.")
flags.DEFINE_float("learning_rate_decay_examples", 4000000,
                   "Multiply current learning rate by learning_rate_decay "
                   "every learning_rate_decay_examples.")

# Cyclic learning rate
flags.DEFINE_float("min_learning_rate", 0.01,
                   "Define the minimum learning_rate used for cyclic lr")
flags.DEFINE_float("max_learning_rate", 0.1,
                   "Define the maximum learning_rate used for cyclic lr")
flags.DEFINE_integer("step_size_learning_rate", 20,
                     "Define the step size for cyclic_learning_rate")
flags.DEFINE_string("mode_cyclic_learning_rate", "triangular",
                    "Define the polices for the 'cyclic_learning_rate'"
                    "Choices are ['triangular', 'triangular2', 'exp_range']."
                    "Default is 'triangular'.")
flags.DEFINE_float("gamma", 0.99994,
                   "Constant in 'exp_range' mode: gamma**(global_step)")


def _cyclic_learning_rate(global_step,
                         learning_rate=0.01,
                         max_lr=0.1,
                         step_size=20.,
                         gamma=0.99994,
                         mode='triangular',
                         name=None):
  """
    function taken from: https://goo.gl/x4drQS
    Applies cyclic learning rate (CLR).
    From the paper:
    Smith, Leslie N.
    "Cyclical learning rates for training neural networks." 2017.
    [https://arxiv.org/pdf/1506.01186.pdf]
    This method lets the learning rate cyclically vary between reasonable
    boundary values achieving improved classification accuracy and often in
    fewer iterations. This code varies the learning rate linearly between the
    minimum (learning_rate) and the maximum (max_lr).

    It returns the cyclic learning rate. It is computed as:
       ```python
       cycle = floor( 1 + global_step /
        ( 2 * step_size ) )
      x = abs( global_step / step_size – 2 * cycle + 1 )
      clr = learning_rate +
        ( max_lr – learning_rate ) * max( 0 , 1 - x )
       ```
      Polices:
        'triangular':
          Default, linearly increasing then linearly decreasing the
          learning rate at each cycle.
         'triangular2':
          The same as the triangular policy except the learning
          rate difference is cut in half at the end of each cycle.
          This means the learning rate difference drops after each cycle.
         'exp_range':
          The learning rate varies between the minimum and maximum
          boundaries and each boundary value declines by an exponential
          factor of: gamma^global_step.
       Example: 'triangular2' mode cyclic learning rate.
        '''python
        ...
        global_step = tf.Variable(0, trainable=False)
        optimizer = tf.train.AdamOptimizer(learning_rate=
          clr.cyclic_learning_rate(global_step=global_step, mode='triangular2'))
        train_op = optimizer.minimize(loss_op, global_step=global_step)
        ...
         with tf.Session() as sess:
            sess.run(init)
            for step in range(1, num_steps+1):
              assign_op = global_step.assign(step)
              sess.run(assign_op)
        ...
         '''
       Args:
        global_step: A scalar `int32` or `int64` `Tensor` or a Python number.
          Global step to use for the cyclic computation.  Must not be negative.
        learning_rate: A scalar `float32` or `float64` `Tensor` or a
        Python number.  The initial learning rate which is the lower bound
          of the cycle (default = 0.1).
        max_lr:  A scalar. The maximum learning rate boundary.
        step_size: A scalar. The number of iterations in half a cycle.
          The paper suggests step_size = 2-8 x training iterations in epoch.
        gamma: constant in 'exp_range' mode:
          gamma**(global_step)
        mode: one of {triangular, triangular2, exp_range}.
            Default 'triangular'.
            Values correspond to policies detailed above.
        name: String.  Optional name of the operation.  Defaults to
          'CyclicLearningRate'.
       Returns:
        A scalar `Tensor` of the same type as `learning_rate`.  The cyclic
        learning rate.
      Raises:
        ValueError: if `global_step` is not supplied.
      @compatibility(eager)
      When eager execution is enabled, this function returns
      a function which in turn returns the decayed learning
      rate Tensor. This can be useful for changing the learning
      rate value across different invocations of optimizer functions.
      @end_compatibility
  """
  if global_step is None:
    raise ValueError("global_step is required for cyclic_learning_rate.")
  
  with ops.name_scope(name, "CyclicLearningRate", 
    [learning_rate, global_step]) as name:
    learning_rate = ops.convert_to_tensor(learning_rate, name="learning_rate")
    dtype = learning_rate.dtype
    global_step = math_ops.cast(global_step, dtype)
    step_size = math_ops.cast(step_size, dtype)
    
    def cyclic_lr():
      """Helper to recompute learning rate; most helpful in eager-mode."""
      
      # computing: cycle = floor( 1 + global_step / ( 2 * step_size ) )
      double_step = math_ops.multiply(2., step_size)
      global_div_double_step = math_ops.divide(global_step, double_step)
      cycle = math_ops.floor(math_ops.add(1., global_div_double_step))
      
      # computing: x = abs( global_step / step_size – 2 * cycle + 1 )
      double_cycle = math_ops.multiply(2., cycle)
      global_div_step = math_ops.divide(global_step, step_size)
      tmp = math_ops.subtract(global_div_step, double_cycle)
      x = math_ops.abs(math_ops.add(1., tmp))
      
      # computing: clr = learning_rate + (max_lr – learning_rate) * max(0, 1 - x)
      a1 = math_ops.maximum(0., math_ops.subtract(1., x))
      a2 = math_ops.subtract(max_lr, learning_rate)
      clr = math_ops.multiply(a1, a2)
      
      if mode == 'triangular2':
        clr = math_ops.divide(clr, math_ops.cast(math_ops.pow(2, math_ops.cast(
            cycle-1, tf.int32)), tf.float32))
      if mode == 'exp_range':
        clr = math_ops.multiply(math_ops.pow(gamma, global_step), clr)
      return math_ops.add(clr, learning_rate, name=name)
     
    if not context.executing_eagerly():
      cyclic_lr = cyclic_lr()
    return cyclic_lr


class LearningRate:

  def __init__(self, global_step, batch_size):
    self.global_step = global_step
    self.batch_size = batch_size

  def piecewise_constant(self):
    boundaries = list(map(int, FLAGS.boundaries.split(',')))
    values = list(map(float, FLAGS.values.split(',')))
    assert len(boundaries) == (len(values) + 1)
    learning_rate = tf.train.piecewise_constant(
      self.global_step, 
      boundaries=boundaries, 
      values=values)
    return learning_rate

  def exponential_decay(self):
    learning_rate = tf.train.exponential_decay(
        FLAGS.base_learning_rate,
        self.global_step * self.batch_size,
        FLAGS.learning_rate_decay_examples,
        FLAGS.learning_rate_decay,
        staircase=True)
    return learning_rate

  def cyclic_learning_rate(self):
    learning_rate = _cyclic_learning_rate(
        self.global_step,
        learning_rate=FLAGS.base_learning_rate,
        max_lr=FLAGS.max_learning_rate,
        step_size=FLAGS.step_size_learning_rate,
        gamma=FLAGS.gamma,
        mode=FLAGS.mode_cyclic_learning_rate)
    return learning_rate

  def get_learning_rate(self):
    strategy = FLAGS.learning_rate_strategy
    logging.info("Using '{}' strategy for learning rate".format(strategy))
    learning_rate = getattr(self, strategy)()
    tf.summary.scalar('learning_rate', learning_rate)
    return learning_rate