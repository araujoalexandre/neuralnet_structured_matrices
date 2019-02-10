
import numpy as np
import tensorflow as tf


def make_summary(name, value, summary_writer, global_step_val):
  """Creates a tf.Summary proto with the given name and value."""
  summary = tf.Summary()
  val = summary.value.add()
  val.tag = str(name)
  val.simple_value = float(value)
  summary_writer.add_summary(summary, global_step_val)


def MakeSummary(name, value):
  """Creates a tf.Summary proto with the given name and value."""
  summary = tf.Summary()
  val = summary.value.add()
  val.tag = str(name)
  val.simple_value = float(value)
  return summary

def summary_histogram(writer, tag, values, step, bins=1000):

  # Create histogram using numpy
  counts, bin_edges = np.histogram(values, bins=bins)

  # Fill fields of histogram proto
  hist = tf.HistogramProto()
  hist.min = float(np.min(values))
  hist.max = float(np.max(values))
  hist.num = int(np.prod(values.shape))
  hist.sum = float(np.sum(values))
  hist.sum_squares = float(np.sum(values**2))

  # Requires equal number as bins, where the first goes from -DBL_MAX to bin_edges[1]
  # See https://github.com/tensorflow/tensorflow/blob/master/tensorflow/core/framework/summary.proto#L30
  # Thus, we drop the start of the first bin
  bin_edges = bin_edges[1:]

  # Add bin edges and counts
  for edge in bin_edges:
      hist.bucket_limit.append(edge)
  for c in counts:
      hist.bucket.append(c)

  # Create and write Summary
  summary = tf.Summary(value=[tf.Summary.Value(tag=tag, histo=hist)])
  writer.add_summary(summary, step)
  writer.flush()


def l1_normalize(x, dim, epsilon=1e-12, name=None):
  """Normalizes along dimension `dim` using an L1 norm.
  For a 1-D tensor with `dim = 0`, computes
      output = x / max(sum(abs(x)), epsilon)
  For `x` with more dimensions, independently normalizes each 1-D slice along
  dimension `dim`.
  Args:
    x: A `Tensor`.
    dim: Dimension along which to normalize.  A scalar or a vector of
      integers.
    epsilon: A lower bound value for the norm. Will use `sqrt(epsilon)` as the
      divisor if `norm < sqrt(epsilon)`.
    name: A name for this operation (optional).
  Returns:
    A `Tensor` with the same shape as `x`.
  """
  with tf.name_scope(name, "l1_normalize", [x]) as name:
    abs_sum = tf.reduce_sum(tf.abs(x), dim, keep_dims = True)
    x_inv_norm = tf.reciprocal(tf.maximum(abs_sum, epsilon))
    return tf.multiply(x, x_inv_norm, name=name)

def Dequantize(feat_vector, max_quantized_value=2, min_quantized_value=-2):
  """Dequantize the feature from the byte format to the float format.

  Args:
    feat_vector: the input 1-d vector.
    max_quantized_value: the maximum of the quantized value.
    min_quantized_value: the minimum of the quantized value.

  Returns:
    A float vector which has the same shape as feat_vector.
  """
  assert max_quantized_value > min_quantized_value
  quantized_range = max_quantized_value - min_quantized_value
  scalar = quantized_range / 255.0
  bias = (quantized_range / 512.0) + min_quantized_value
  return feat_vector * scalar + bias

def AddGlobalStepSummary(summary_writer,
                         global_step_val,
                         global_step_info_dict,
                         summary_scope="Eval"):
  """Add the global_step summary to the Tensorboard.

  Args:
    summary_writer: Tensorflow summary_writer.
    global_step_val: a int value of the global step.
    global_step_info_dict: a dictionary of the evaluation metrics calculated for
      a mini-batch.
    summary_scope: Train or Eval.

  Returns:
    A string of this global_step summary
  """
  this_hit_at_one = global_step_info_dict["hit_at_one"]
  this_perr = global_step_info_dict["perr"]
  this_loss = global_step_info_dict["loss"]
  examples_per_second = global_step_info_dict.get("examples_per_second", -1)

  summary_writer.add_summary(
      MakeSummary("GlobalStep/" + summary_scope + "_Hit@1", this_hit_at_one),
      global_step_val)
  summary_writer.add_summary(
      MakeSummary("GlobalStep/" + summary_scope + "_Perr", this_perr),
      global_step_val)
  summary_writer.add_summary(
      MakeSummary("GlobalStep/" + summary_scope + "_Loss", this_loss),
      global_step_val)

  if examples_per_second != -1:
    summary_writer.add_summary(
        MakeSummary("GlobalStep/" + summary_scope + "_Example_Second",
                    examples_per_second), global_step_val)

  summary_writer.flush()
  info = ("global_step {0} | Batch Hit@1: {1:.3f} | Batch PERR: {2:.3f} | Batch Loss: {3:.3f} "
          "| Examples_per_sec: {4:.3f}").format(
              global_step_val, this_hit_at_one, this_perr, this_loss,
              examples_per_second)
  return info


def AddEpochSummary(summary_writer,
                    global_step_val,
                    epoch_info_dict,
                    summary_scope="Eval"):
  """Add the epoch summary to the Tensorboard.

  Args:
    summary_writer: Tensorflow summary_writer.
    global_step_val: a int value of the global step.
    epoch_info_dict: a dictionary of the evaluation metrics calculated for the
      whole epoch.
    summary_scope: Train or Eval.

  Returns:
    A string of this global_step summary
  """
  epoch_id = epoch_info_dict["epoch_id"]
  avg_hit_at_one = epoch_info_dict["avg_hit_at_one"]
  avg_perr = epoch_info_dict["avg_perr"]
  avg_loss = epoch_info_dict["avg_loss"]
  aps = epoch_info_dict["aps"]
  gap = epoch_info_dict["gap"]
  mean_ap = np.mean(aps)

  summary_writer.add_summary(
      MakeSummary("Epoch/" + summary_scope + "_Avg_Hit@1", avg_hit_at_one),
      global_step_val)
  summary_writer.add_summary(
      MakeSummary("Epoch/" + summary_scope + "_Avg_Perr", avg_perr),
      global_step_val)
  summary_writer.add_summary(
      MakeSummary("Epoch/" + summary_scope + "_Avg_Loss", avg_loss),
      global_step_val)
  summary_writer.add_summary(
      MakeSummary("Epoch/" + summary_scope + "_MAP", mean_ap),
          global_step_val)
  summary_writer.add_summary(
      MakeSummary("Epoch/" + summary_scope + "_GAP", gap),
          global_step_val)
  summary_writer.flush()

  info = ("epoch/eval number {0} | Avg_Hit@1: {1:.3f} | Avg_PERR: {2:.3f} "
          "| MAP: {3:.3f} | GAP: {4:.3f} | Avg_Loss: {5:3f}").format(
          epoch_id, avg_hit_at_one, avg_perr, mean_ap, gap, avg_loss)
  return info


class MessageBuilder:

  def __init__(self):
    self.msg = []

  def add(self, name, value, format=None):
    metric_str = "{}: ".format(name)
    if fill:
      metric_str += "{x:^{format}}".format(x=value, format=format)
    else:
      metric_str += "{}".format(value)
    self.msg.append(metric_str)

  def get_message(self):
    return " | ".join(self.msg)


