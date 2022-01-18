import math
import os
from random import shuffle

import cv2
import numpy as np
from PIL import Image
from tensorflow import keras

from utils.utils import cvtColor, preprocess_input


class DeeplabDataset(keras.utils.Sequence):
    def __init__(self, annotation_lines, input_shape, batch_size, num_classes, train, dataset_path, JPEGImages="VOC2007/JPEGImages", Labels = "VOC2007/SegmentationClass"):
        self.annotation_lines   = annotation_lines
        self.length             = len(self.annotation_lines)
        self.input_shape        = input_shape
        self.batch_size         = batch_size
        self.num_classes        = num_classes
        self.train              = train
        self.dataset_path       = dataset_path
        self.JPEGImages_path = JPEGImages
        self.Labels_path = Labels

    def __len__(self):
        return math.ceil(len(self.annotation_lines) / float(self.batch_size))

    def __getitem__(self, index):
        images  = []
        targets = []
        for i in range(index * self.batch_size, (index + 1) * self.batch_size):  
            i = i % self.length
            name = self.annotation_lines[i].split()[0]
            jpg = Image.open(os.path.join(os.path.join(self.dataset_path, self.JPEGImages_path), name + ".png"))
            png = Image.open(os.path.join(os.path.join(self.dataset_path, self.Labels_path), name + ".png"))
            # 数据增强
            jpg, png = self.get_random_data(jpg, png, self.input_shape, random = self.train)
            jpg = preprocess_input(np.array(jpg, np.float64))
            png = np.array(png)
            png[png >= self.num_classes] = self.num_classes
            # 将标签转换成one-hot的形式
            seg_labels = np.eye(self.num_classes + 1)[png.reshape([-1])]
            seg_labels = seg_labels.reshape((int(self.input_shape[1]), int(self.input_shape[0]), self.num_classes+1))

            images.append(jpg)
            targets.append(seg_labels)

        images = np.array(images)
        targets = np.array(targets)
        return images, targets

    def __call__(self):
        i = 0
        while True:
            images  = []
            targets = []
            for b in range(self.batch_size):
                if i==0:
                    np.random.shuffle(self.annotation_lines)
                name        = self.annotation_lines[i].split()[0]
                # 读取标签
                jpg = Image.open(os.path.join(os.path.join(self.dataset_path, self.JPEGImages_path), name + ".jpg"))
                png = Image.open(os.path.join(os.path.join(self.dataset_path, self.Labels_path), name + ".png"))
                jpg, png = self.get_random_data(jpg, png, self.input_shape, random = self.train)
                jpg = preprocess_input(np.array(jpg, np.float64))
                png = np.array(png)
                png[png >= self.num_classes] = self.num_classes
                # 标签转换成one-hot形式
                seg_labels = np.eye(self.num_classes + 1)[png.reshape([-1])]
                seg_labels = seg_labels.reshape((int(self.input_shape[1]), int(self.input_shape[0]), self.num_classes+1))

                images.append(jpg)
                targets.append(seg_labels)
                i = (i + 1) % self.length
                
            images = np.array(images)
            targets = np.array(targets)
            yield images, targets
            
    def rand(self, a=0, b=1):
        return np.random.rand() * (b - a) + a

    def get_random_data(self, image, label, input_shape, jitter=.3, hue=.1, sat=1.5, val=1.5, random=True):
        image = cvtColor(image)
        label = Image.fromarray(np.array(label))
        h, w = input_shape

        if not random:
            iw, ih = image.size
            scale = min(w/iw, h/ih)
            nw = int(iw*scale)
            nh = int(ih*scale)

            image = image.resize((nw,nh), Image.BICUBIC)
            new_image = Image.new('RGB', [w, h], (128,128,128))
            new_image.paste(image, ((w-nw)//2, (h-nh)//2))

            label = label.resize((nw,nh), Image.NEAREST)
            new_label = Image.new('L', [w, h], (0))
            new_label.paste(label, ((w-nw)//2, (h-nh)//2))
            return new_image, new_label

        # resize image
        rand_jit1 = self.rand(1-jitter,1+jitter)
        rand_jit2 = self.rand(1-jitter,1+jitter)
        new_ar = w/h * rand_jit1/rand_jit2

        scale = self.rand(0.25, 2)
        if new_ar < 1:
            nh = int(scale*h)
            nw = int(nh*new_ar)
        else:
            nw = int(scale*w)
            nh = int(nw/new_ar)

        image = image.resize((nw,nh), Image.BICUBIC)
        label = label.resize((nw,nh), Image.NEAREST)
        
        flip = self.rand()<.5
        if flip: 
            image = image.transpose(Image.FLIP_LEFT_RIGHT)
            label = label.transpose(Image.FLIP_LEFT_RIGHT)
        
        # place image
        dx = int(self.rand(0, w-nw))
        dy = int(self.rand(0, h-nh))
        new_image = Image.new('RGB', (w,h), (128,128,128))
        new_label = Image.new('L', (w,h), (0))
        new_image.paste(image, (dx, dy))
        new_label.paste(label, (dx, dy))
        image = new_image
        label = new_label

        # distort image
        hue = self.rand(-hue, hue)
        sat = self.rand(1, sat) if self.rand()<.5 else 1/self.rand(1, sat)
        val = self.rand(1, val) if self.rand()<.5 else 1/self.rand(1, val)
        x = cv2.cvtColor(np.array(image,np.float32)/255, cv2.COLOR_RGB2HSV)
        x[..., 0] += hue*360
        x[..., 0][x[..., 0]>1] -= 1
        x[..., 0][x[..., 0]<0] += 1
        x[..., 1] *= sat
        x[..., 2] *= val
        x[x[:,:, 0]>360, 0] = 360
        x[:, :, 1:][x[:, :, 1:]>1] = 1
        x[x<0] = 0
        image_data = cv2.cvtColor(x, cv2.COLOR_HSV2RGB)*255
        return image_data,label

    def on_epoch_begin(self):
        shuffle(self.annotation_lines)