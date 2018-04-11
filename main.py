import os.path
import tensorflow as tf
import helper
import warnings
from distutils.version import LooseVersion
import project_tests as tests
from moviepy.editor import *
import matplotlib.pyplot as plt

# Check TensorFlow Version
assert LooseVersion(tf.__version__) >= LooseVersion('1.0'), 'Please use TensorFlow version 1.0 or newer.  You are using {}'.format(tf.__version__)
print('TensorFlow Version: {}'.format(tf.__version__))

# Check for a GPU
if not tf.test.gpu_device_name():
    warnings.warn('No GPU found. Please use a GPU to train your neural network.')
else:
    print('Default GPU Device: {}'.format(tf.test.gpu_device_name()))


def load_vgg(sess, vgg_path):
    """
    Load Pretrained VGG Model into TensorFlow.
    :param sess: TensorFlow Session
    :param vgg_path: Path to vgg folder, containing "variables/" and "saved_model.pb"
    :return: Tuple of Tensors from VGG model (image_input, keep_prob, layer3_out, layer4_out, layer7_out)
    """

    vgg_tag = 'vgg16'
    vgg_input_tensor_name = 'image_input:0'
    vgg_keep_prob_tensor_name = 'keep_prob:0'
    vgg_layer3_out_tensor_name = 'layer3_out:0'
    vgg_layer4_out_tensor_name = 'layer4_out:0'
    vgg_layer7_out_tensor_name = 'layer7_out:0'

    tf.saved_model.loader.load(sess, [vgg_tag], vgg_path)
    graph = tf.get_default_graph()
    image_input = graph.get_tensor_by_name(vgg_input_tensor_name)
    keep_prob = graph.get_tensor_by_name(vgg_keep_prob_tensor_name)
    layer3_out = graph.get_tensor_by_name(vgg_layer3_out_tensor_name)
    layer4_out = graph.get_tensor_by_name(vgg_layer4_out_tensor_name)
    layer7_out = graph.get_tensor_by_name(vgg_layer7_out_tensor_name)
    
    return image_input, keep_prob, layer3_out, layer4_out, layer7_out
tests.test_load_vgg(load_vgg, tf)


def layers(vgg_layer3_out, vgg_layer4_out, vgg_layer7_out, num_classes):
    """
    Create the layers for a fully convolutional network.  Build skip-layers using the vgg layers.
    :param vgg_layer3_out: TF Tensor for VGG Layer 3 output
    :param vgg_layer4_out: TF Tensor for VGG Layer 4 output
    :param vgg_layer7_out: TF Tensor for VGG Layer 7 output
    :param num_classes: Number of classes to classify
    :return: The Tensor for the last layer of output
    """
    stddev = 0.01
    l2_reg = 1e-3

    input = tf.layers.conv2d(vgg_layer7_out, num_classes, 1, padding='SAME', kernel_initializer=tf.random_normal_initializer(stddev=stddev), kernel_regularizer=tf.contrib.layers.l2_regularizer(l2_reg))

    output = tf.layers.conv2d_transpose(input, num_classes, 4, strides=(2, 2), padding='SAME', kernel_initializer=tf.random_normal_initializer(stddev=stddev), kernel_regularizer=tf.contrib.layers.l2_regularizer(l2_reg))

    vgg_layer4_out_conv = tf.layers.conv2d(vgg_layer4_out, num_classes, 1,  padding='SAME', kernel_initializer=tf.random_normal_initializer(stddev=stddev), kernel_regularizer=tf.contrib.layers.l2_regularizer(l2_reg))
    # tf.Print(output, [tf.shape(output)])
    # tf.Print(vgg_layer4_out, [tf.shape(vgg_layer4_out)])
    # tf.Print(vgg_layer4_out_conv, [tf.shape(vgg_layer4_out_conv)])

    input = tf.add(output, vgg_layer4_out_conv)
    input = tf.layers.conv2d_transpose(input, num_classes, 4, strides=(2, 2), padding='SAME', kernel_initializer=tf.random_normal_initializer(stddev=stddev), kernel_regularizer=tf.contrib.layers.l2_regularizer(l2_reg))

    vgg_layer3_out_conv = tf.layers.conv2d(vgg_layer3_out, num_classes, 1,  padding='SAME', kernel_initializer=tf.random_normal_initializer(stddev=stddev), kernel_regularizer=tf.contrib.layers.l2_regularizer(l2_reg))
    input = tf.add(input, vgg_layer3_out_conv)
    input = tf.layers.conv2d_transpose(input, num_classes, 16, strides=(8, 8),  padding='SAME', kernel_initializer=tf.random_normal_initializer(stddev=stddev), kernel_regularizer=tf.contrib.layers.l2_regularizer(l2_reg))
    return input
tests.test_layers(layers)


def optimize(nn_last_layer, correct_label, learning_rate, num_classes):
    """
    Build the TensorFLow loss and optimizer operations.
    :param nn_last_layer: TF Tensor of the last layer in the neural network
    :param correct_label: TF Placeholder for the correct label image
    :param learning_rate: TF Placeholder for the learning rate
    :param num_classes: Number of classes to classify
    :return: Tuple of (logits, train_op, cross_entropy_loss)
    """

    logits = tf.reshape(nn_last_layer, (-1, num_classes))
    correct_label = tf.reshape(correct_label, (-1, num_classes))
    cross_entropy_loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=logits, labels=correct_label))

    train_op = tf.train.AdamOptimizer(learning_rate).minimize(cross_entropy_loss)

    return logits, train_op, cross_entropy_loss
tests.test_optimize(optimize)


def train_nn(sess, epochs, batch_size, get_batches_fn, train_op, cross_entropy_loss, input_image,
             correct_label, keep_prob, learning_rate):
    """
    Train neural network and print out the loss during training.
    :param sess: TF Session
    :param epochs: Number of epochs
    :param batch_size: Batch size
    :param get_batches_fn: Function to get batches of training data.  Call using get_batches_fn(batch_size)
    :param train_op: TF Operation to train the neural network
    :param cross_entropy_loss: TF Tensor for the amount of loss
    :param input_image: TF Placeholder for input images
    :param correct_label: TF Placeholder for label images
    :param keep_prob: TF Placeholder for dropout keep probability
    :param learning_rate: TF Placeholder for learning rate
    """

    sess.run(tf.global_variables_initializer())
    iterations = []
    losses = []
    iteration = 0
    for epoch in range(epochs):
        for image, label in get_batches_fn(batch_size):
            feed = {input_image: image,
                    correct_label: label,
                    keep_prob: 0.5,
                    learning_rate: 0.001}
            _, loss = sess.run([train_op, cross_entropy_loss], feed_dict=feed)
            iterations.append(iteration)
            losses.append(loss)
            if iteration % 10 == 0:
                print("Epoch: {}/{}...".format(epoch+1, epochs),
                      "Iteration: {}".format(iteration),
                      "Training loss: {:.5f}".format(loss))
            iteration += 1

    plt.plot(iterations, losses, 'ro')
    plt.savefig('runs/training.png')

tests.test_train_nn(train_nn)

def run():
    num_classes = 2
    image_shape = (160, 576)
    data_dir = './data'
    runs_dir = './runs'
    tests.test_for_kitti_dataset(data_dir)

    # Download pretrained vgg model
    helper.maybe_download_pretrained_vgg(data_dir)

    # Hyperparameters
    epochs = 20
    batch_size = 5

    # 20,20,stddev=0.01 - Epoch: 20/20... Iteration: 290 Training loss: 0.09508
    # 20,10,stddev=0.01 - Epoch: 20/20... Iteration: 570 Training loss: 0.07547
    # 40,5,stddev=0.01 - Epoch: 40/40... Iteration: 2310 Training loss: 0.02939
    # 40,5,stddev=0.001 - Epoch: 40/40... Iteration: 2310 Training loss: 0.03463
    # 20,5,stddev=0.01 - Epoch: 20/20... Iteration: 1150 Training loss: 0.06885

    # OPTIONAL: Train and Inference on the cityscapes dataset instead of the Kitti dataset.
    # You'll need a GPU with at least 10 teraFLOPS to train on.
    #  https://www.cityscapes-dataset.com/


    with tf.Session() as sess:
        # Path to vgg model
        vgg_path = os.path.join(data_dir, 'vgg')
        # Create function to get batches
        get_batches_fn = helper.gen_batch_function(os.path.join(data_dir, 'data_road/training'), image_shape)

        # OPTIONAL: Augment Images for better results
        #  https://datascience.stackexchange.com/questions/5224/how-to-prepare-augment-images-for-neural-network

        correct_label = tf.placeholder(tf.int32, [None, None, None, num_classes], name='correct_label')
        learning_rate = tf.placeholder(tf.float32, name='learning_rate')

        # Build NN using load_vgg, layers, and optimize function
        image_input, keep_prob, layer3_out, layer4_out, layer7_out = load_vgg(sess, vgg_path)
        layer_output = layers(layer3_out, layer4_out, layer7_out, num_classes)

        saver = tf.train.Saver()

        # Train NN using the train_nn function
        logits, train_op, cross_entropy_loss = optimize(layer_output, correct_label, learning_rate, num_classes)
        train_nn(sess, epochs, batch_size, get_batches_fn, train_op, cross_entropy_loss, image_input, correct_label, keep_prob, learning_rate)

        # Save inference data using helper.save_inference_samples
        helper.save_inference_samples(runs_dir, data_dir, sess, image_shape, logits, keep_prob, image_input)

        saver.save(sess, './runs/model.ckpt')

        # OPTIONAL: Apply the trained model to a video
        clip = VideoFileClip("challenge_video.mp4")
        new_frames = [helper.render_image(sess, logits, keep_prob, image_input, frame, image_shape) for frame in clip.iter_frames()]
        new_clip = ImageSequenceClip(new_frames, fps=clip.fps)
        new_clip.write_videofile("new_file.mp4")

if __name__ == '__main__':
    run()