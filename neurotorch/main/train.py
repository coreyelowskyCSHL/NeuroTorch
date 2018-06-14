from neurotorch.core.Trainer import Trainer
from neurotorch.datasets.TiffDataset import TiffDataset
from neurotorch.nets.NetCollector import NetCollector
from neurotorch.nets.RSUNet import RSUNet
import argparse
import importlib


def parse_arguments():
    parser = argparse.ArgumentParser(description='Trains a neural network model')
    parser.add_argument('NET', help="Neural network")
    parser.add_argument('INPUTS', help="Input dataset for training")
    parser.add_argument('LABELS', help="Label dataset for training")
    parser.add_argument('-c', '--checkpoint', help="Checkpoint number",
                        type=int)
    parser.add_argument('-d', '--gpu', help="GPU number for training",
                        type=int)
    parser.add_argument('-n', '--iterations', help="Max iterations for training",
                        type=int)
    

    return parser.parse_args()


def main():
    args = parse_arguments()

    net = NetCollector().get_module(args.NET)

    inputs = TiffDataset(args.INPUTS)
    labels = TiffDataset(args.LABELS)

    kwargs = dict()

    if args.checkpoint:
        kwargs["checkpoint"] = args.checkpoint

    if args.iterations:
        kwargs["max_epochs"] = args.iterations

    if args.gpu:
        kwargs["gpu_device"] = args.gpu

    trainer = Trainer(net, inputs, labels, **kwargs)

    trainer.run_training()


if __name__ == '__main__':
    main()
