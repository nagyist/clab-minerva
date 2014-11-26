import math
import sys
import time
import numpy as np
import owl
import Queue
from owl.conv import *
import owl.elewise as ele

class AlexModel:
    def __init__(self):
        self.weights = []
	self.weightsdelta = []
        self.bias = []
        self.biasdelta = []
	self.conv_infos = [
            conv_info(0, 0, 4, 4), # conv1
            conv_info(2, 2, 1, 1), # conv2
            conv_info(1, 1, 1, 1), # conv3
            conv_info(1, 1, 1, 1), # conv4
            conv_info(1, 1, 1, 1)  # conv5
        ];
        self.pooling_infos = [
            pooling_info(3, 3, 2, 2, pool_op.max), # pool1
            pooling_info(3, 3, 2, 2, pool_op.max), # pool2
            pooling_info(3, 3, 2, 2, pool_op.max)  # pool5
        ];

    def init_random(self):
        self.weights = [
            owl.randn([11, 11, 3, 96], 0.0, 0.1),
            owl.randn([5, 5, 96, 256], 0.0, 0.1),
            owl.randn([3, 3, 256, 384], 0.0, 0.1),
            owl.randn([3, 3, 384, 384], 0.0, 0.1),
            owl.randn([3, 3, 384, 256], 0.0, 0.1),
            owl.randn([4096, 9216], 0.0, 0.1),
            owl.randn([4096, 4096], 0.0, 0.1),
            owl.randn([1000, 4096], 0.0, 0.1)
        ];

	self.weightsdelta = [
            owl.zeros([11, 11, 3, 96]),
            owl.zeros([5, 5, 96, 256]),
            owl.zeros([3, 3, 256, 384]),
            owl.zeros([3, 3, 384, 384]),
            owl.zeros([3, 3, 384, 256]),
            owl.zeros([4096, 9216]),
            owl.zeros([4096, 4096]),
            owl.zeros([1000, 4096])
        ];


        self.bias = [
            owl.zeros([96]),
            owl.zeros([256]),
            owl.zeros([384]),
            owl.zeros([384]),
            owl.zeros([256]),
            owl.zeros([4096, 1]),
            owl.zeros([4096, 1]),
            owl.zeros([1000, 1])
        ];

        self.biasdelta = [
            owl.zeros([96]),
            owl.zeros([256]),
            owl.zeros([384]),
            owl.zeros([384]),
            owl.zeros([256]),
            owl.zeros([4096, 1]),
            owl.zeros([4096, 1]),
            owl.zeros([1000, 1])
        ];

def print_training_accuracy(o, t, minibatch_size):
    predict = o.max_index(0)
    ground_truth = t.max_index(0)
    correct = (predict - ground_truth).count_zero()
    print 'Training error: {}'.format((minibatch_size - correct) * 1.0 / minibatch_size)

def train_network(model, data, label,
                  num_epochs = 100, num_train_samples = 100000, minibatch_size = 256,
                  num_minibatches = 390, dropout_rate = 0.5, eps_w = 1, eps_b = 1, momemtum = 0.9, wd = 0.005):
    eps_w = eps_w / minibatch_size
    eps_b = eps_b / minibatch_size
    gpu = owl.create_gpu_device(0)
    owl.set_device(gpu)
    num_layers = 20
    count = 0
    last = time.time()
    for i in xrange(num_epochs):
        print "Epoch #", i, ", time: %s" % (time.time() - last)
        for j in xrange(num_minibatches):
            acts = [None] * num_layers
            sens = [None] * num_layers

            # FF
            acts[0] = owl.randn([227, 227, 3, minibatch_size], 0.0, 0.1) # data
            target = owl.randn([1000, minibatch_size], 0.0, 0.1) # label

            acts[1] = conv_forward(acts[0], model.weights[0], model.bias[0], model.conv_infos[0]) # conv1
            acts[2] = activation_forward(acts[1], act_op.relu) # relu1
            acts[3] = pooling_forward(acts[2], model.pooling_infos[0]) # pool1

            acts[4] = conv_forward(acts[3], model.weights[1], model.bias[1], model.conv_infos[1]) # conv2
            acts[5] = activation_forward(acts[4], act_op.relu) # relu2
            acts[6] = pooling_forward(acts[5], model.pooling_infos[1]) # pool2

            acts[7] = conv_forward(acts[6], model.weights[2], model.bias[2], model.conv_infos[2]) # conv3
            acts[8] = activation_forward(acts[7], act_op.relu) # relu3
            acts[9] = conv_forward(acts[8], model.weights[3], model.bias[3], model.conv_infos[3]) # conv4
            acts[10] = activation_forward(acts[9], act_op.relu) # relu4

            acts[11] = conv_forward(acts[10], model.weights[4], model.bias[4], model.conv_infos[4]) # conv5
            acts[12] = activation_forward(acts[11], act_op.relu) # relu5
            acts[13] = pooling_forward(acts[12], model.pooling_infos[2]) # pool5

            re_acts13 = acts[13].reshape([np.prod(acts[13].shape[0:3]), minibatch_size])

            acts[14] = model.weights[5] * re_acts13 + model.bias[5] # fc6
            acts[15] = ele.relu(acts[14]) # relu6
            mask6 = owl.randb(acts[15].shape, dropout_rate)
            acts[15] = ele.mult(acts[15], mask6) # drop6

            acts[16] = model.weights[6] * acts[15] + model.bias[6] # fc7
            acts[17] = ele.relu(acts[16]) # relu7
            mask7 = owl.randb(acts[17].shape, dropout_rate)
            acts[17] = ele.mult(acts[17], mask7) # drop7

            acts[18] = model.weights[7] * acts[17] + model.bias[7] # fc8
            acts[18] = owl.softmax(acts[18]) # prob

            sens[18] = acts[18] - target

            # BP
            d_act17 = ele.mult(acts[17], 1 - acts[17])
            sens[17] = model.weights[7].trans() * sens[18] # fc8

            sens[17] = ele.mult(sens[17], mask7) # drop7
            sens[16] = ele.relu_back(sens[17], acts[17], acts[16]) # relu7
            sens[15] = model.weights[6].trans() * sens[16]

            sens[15] = ele.mult(sens[15], mask6) # drop6
            sens[14] = ele.relu_back(sens[15], acts[15], acts[14]) # relu6
            sens[13] = model.weights[5].trans() * sens[14]
            sens[13] = sens[13].reshape(acts[13].shape) # fc6

            sens[12] = pooling_backward(sens[13], acts[13], acts[12], model.pooling_infos[2]) # pool5
            sens[11] = activation_backward(sens[12], acts[12], acts[11], act_op.relu) # relu5
            sens[10] = conv_backward_data(sens[11], model.weights[4], model.conv_infos[4]) # conv5

            sens[9] = activation_backward(sens[10], acts[10], acts[9], act_op.relu) # relu4
            sens[8] = conv_backward_data(sens[9], model.weights[3], model.conv_infos[3]) # conv4
            sens[7] = activation_backward(sens[8], acts[8], acts[7], act_op.relu) # relu3
            sens[6] = conv_backward_data(sens[7], model.weights[2], model.conv_infos[2]) # conv3

            sens[5] = pooling_backward(sens[6], acts[6], acts[5], model.pooling_infos[1]) # pool2
            sens[4] = activation_backward(sens[5], acts[5], acts[4], act_op.relu) # relu2
            sens[3] = conv_backward_data(sens[4], model.weights[1], model.conv_infos[1]) # conv2

            sens[2] = pooling_backward(sens[3], acts[3], acts[2], model.pooling_infos[0]) # pool1
            sens[1] = activation_backward(sens[2], acts[2], acts[1], act_op.relu) # relu1
            sens[0] = conv_backward_data(sens[1], model.weights[0], model.conv_infos[0]) # conv1

	    model.weights[7] -= momemtum * model.weightsdelta[7] - eps_w * (sens[18] * acts[17].trans() + wd * model.weights[7] / minibatch_size)
            model.bias[7] -= momemtum * model.biasdelta[7] - eps_b * (sens[18].sum(1) + wd * model.bias[7] / minibatch_size)
            
	    model.weights[6] -= momemtum * model.weightsdelta[6] - eps_w * (sens[16] * acts[15].trans() + wd * model.weights[6] / minibatch_size)
            model.bias[6] -= momemtum * model.biasdelta[6] - eps_b * (sens[16].sum(1) + wd * model.bias[6] / minibatch_size)
    	    
	    model.weights[5] -= momemtum * model.weightsdelta[5] - eps_w * (sens[14] * re_acts13.trans() + wd * model.weights[5] / minibatch_size)
            model.bias[5] -= momemtum * model.biasdelta[5] - eps_b * (sens[14].sum(1) + wd * model.bias[5] / minibatch_size)
            	
            model.weights[4] -= momemtum * model.weightsdelta[4] - eps_w * (conv_backward_filter(sens[11], acts[10], model.conv_infos[4]) + wd * model.weights[4] / minibatch_size)
	    model.bias[4] -= momemtum * model.biasdelta[4] - eps_b * (conv_backward_bias(sens[11]) + wd * model.bias[4] / minibatch_size)

	    model.weights[3] -= momemtum * model.weightsdelta[3] - eps_w * (conv_backward_filter(sens[9], acts[8], model.conv_infos[3]) + wd * model.weights[3] / minibatch_size)
	    model.bias[3] -= momemtum * model.biasdelta[3] - eps_b * (conv_backward_bias(sens[10]) + wd * model.bias[3] / minibatch_size)

 	    model.weights[2] -= momemtum * model.weightsdelta[2] - eps_w * (conv_backward_filter(sens[7], acts[6], model.conv_infos[2]) + wd * model.weights[2] / minibatch_size)
	    model.bias[2] -= momemtum * model.biasdelta[2] - eps_b * (conv_backward_bias(sens[7]) + wd * model.bias[2] / minibatch_size)

  	    model.weights[1] -= momemtum * model.weightsdelta[1] - eps_w * (conv_backward_filter(sens[4], acts[3], model.conv_infos[1]) + wd * model.weights[1] / minibatch_size)
	    model.bias[1] -= momemtum * model.biasdelta[1] - eps_b * (conv_backward_bias(sens[4]) + wd * model.bias[1] / minibatch_size)

            model.weights[0] -= momemtum * model.weightsdelta[0] - eps_w * (conv_backward_filter(sens[1], acts[0], model.conv_infos[0]) + wd * model.weights[0] / minibatch_size)
	    model.bias[0] -= momemtum * model.biasdelta[0] - eps_b * (conv_backward_bias(sens[1]) + wd * model.bias[0] / minibatch_size)
            ++count

            if count % 1 == 0:
                acts[18].start_eval()
                acts[18].wait_for_eval()

if __name__ == '__main__':
    owl.initialize(sys.argv)
    cpu = owl.create_cpu_device()
    owl.set_device(cpu)
    data = []
    label = []
    model = AlexModel()
    model.init_random()
    train_network(model, data, label)

