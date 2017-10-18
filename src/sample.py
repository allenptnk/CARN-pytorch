import os
import argparse
import numpy as np
from collections import OrderedDict
import torch
import torch.nn as nn
from torch.autograd import Variable
from dataset import TestDataset
from PIL import Image

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str)
    parser.add_argument("--ckpt_path", type=str)
    parser.add_argument("--sample_dir", type=str)
    parser.add_argument("--test_data_dir", type=str, default="dataset/Set5")
    parser.add_argument("--cuda", action="store_true")
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--shave", type=int, default=20)
    parser.add_argument("--self_ensemble", action="store_true")

    return parser.parse_args()


def save_image(tensor, filename):
    tensor = tensor.cpu()
    ndarr = tensor.mul(255).clamp(0, 255).byte().permute(1, 2, 0).numpy()
    im = Image.fromarray(ndarr)
    im.save(filename)


def sample(refiner, dataset, config):
    scale = config.scale
    for step, (hr, lr, name) in enumerate(dataset):
        if "DIV2K" in dataset.name:
            h, w = lr.size()[1:]
            h_half, w_half = int(h/2), int(w/2)
            h_chop, w_chop = h_half + config.shave, w_half + config.shave

            lr_patch = torch.FloatTensor(4, 3, h_chop, w_chop)
            lr_patch[0].copy_(lr[:, 0:h_chop, 0:w_chop])
            lr_patch[1].copy_(lr[:, 0:h_chop, w-w_chop:w])
            lr_patch[2].copy_(lr[:, h-h_chop:h, 0:w_chop])
            lr_patch[3].copy_(lr[:, h-h_chop:h, w-w_chop:w])
            lr_patch = Variable(lr_patch, volatile=True).cuda()
            
            sr = refiner(lr_patch).data
            
            h, h_half, h_chop = h*scale, h_half*scale, h_chop*scale
            w, w_half, w_chop = w*scale, w_half*scale, w_chop*scale

            result = torch.FloatTensor(3, h, w).cuda()
            result[:, 0:h_half, 0:w_half].copy_(sr[0, :, 0:h_half, 0:w_half])
            result[:, 0:h_half, w_half:w].copy_(sr[1, :, 0:h_half, w_chop-w+w_half:w_chop])
            result[:, h_half:h, 0:w_half].copy_(sr[2, :, h_chop-h+h_half:h_chop, 0:w_half])
            result[:, h_half:h, w_half:w].copy_(sr[3, :, h_chop-h+h_half:h_chop, w_chop-w+w_half:w_chop])
            sr = result
        else:
            lr = Variable(lr.unsqueeze(0), volatile=True).cuda()
            sr = refiner(lr).data[0]

        model_name = config.ckpt_path.split(".")[0].split("/")[-1]
        sr_dir = os.path.join(config.sample_dir,
                              model_name, 
                              config.test_data_dir.split("/")[-1],
                              "SRx{}".format(config.scale))
        hr_dir = os.path.join(config.sample_dir,
                              model_name, 
                              config.test_data_dir.split("/")[-1],
                              "HR")
        
        if not os.path.exists(sr_dir):
            os.makedirs(sr_dir)
            
        if not os.path.exists(hr_dir):
            os.makedirs(hr_dir)

        sr_im_path = os.path.join(sr_dir, "{}".format(name))
        hr_im_path = os.path.join(hr_dir, "{}".format(name))

        save_image(sr, sr_im_path)
        save_image(hr, hr_im_path)
        print("Saved {}".format(sr_im_path))


def main(config):
    if config.model in ["mdrn"]:
        from model.mdrn import MDRN
        refiner = MDRN(config.scale)
    elif config.model in ["base"]:
        from model.base import MDRN
        refiner = MDRN(config.scale)
    elif config.model in ["mdrn_v2"]:
        from model.mdrn_v2 import MDRN
        refiner = MDRN(config.scale) 
    else:
        raise NotImplementedError("{} is not in our list".format(model_name))
    
    state_dict = torch.load(config.ckpt_path)
    new_state_dict = OrderedDict()
    for k, v in state_dict.items():
        name = k
        # name = k[7:] # remove "module."
        new_state_dict[name] = v
    refiner.load_state_dict(new_state_dict)

    if config.cuda:
        refiner.cuda()
    
    dataset = TestDataset(config.test_data_dir, 
                          config.scale, 
                          config.self_ensemble)
    sample(refiner, dataset, config)
 

if __name__ == "__main__":
    config = parse_args()
    main(config)
