import torch
import torch.optim as optim
import torch.nn as nn
from torch.autograd import Variable
from torch.utils.data import DataLoader
from neurotorch.datasets.dataset import AlignedVolume, TorchVolume
import torch.cuda
import numpy as np


class Trainer(object):
    """
    Trains a PyTorch neural network with a given input and label dataset
    """
    def __init__(self, net, aligned_volume, checkpoint=None,
                 optimizer=None, criterion=None, max_epochs=10,
                 gpu_device=None, validation_split=0.2):
        """
        Sets up the parameters for training

        :param net: A PyTorch neural network
        :param inputs_volume: A PyTorch dataset containing inputs
        :param labels_volume: A PyTorch dataset containing corresponding labels
        """
        self.max_epochs = max_epochs

        self.device = torch.device("cuda:{}".format(gpu_device)
                                   if gpu_device is not None
                                   else "cpu")

        self.net = net.to(self.device)

        if checkpoint is not None:
            self.net.load_state_dict(torch.load(checkpoint))

        if optimizer is None:
            self.optimizer = optim.Adam(self.net.parameters())
        else:
            self.optimizer = optimizer(self.net.parameters())

        if criterion is None:
            self.criterion = nn.BCEWithLogitsLoss()
        else:
            self.criterion = criterion

        if gpu_device is not None:
            self.gpu_device = gpu_device
            self.useGpu = True

        self.volume = TorchVolume(aligned_volume)

    def run_epoch(self, sample_batch):
        """
        Runs an epoch with a given batch of samples

        :param sample_batch: A dictionary containing inputs and labels with the keys 
"input" and "label", respectively
        """
        inputs = Variable(sample_batch[0]).float()
        labels = Variable(sample_batch[1]).float()

        inputs, labels = inputs.to(self.device), labels.to(self.device)

        self.optimizer.zero_grad()

        outputs = self.net(inputs)

        loss = self.criterion(torch.cat(outputs), labels)
        loss_hist = loss.cpu().item()
        loss.backward()
        self.optimizer.step()

        return loss_hist

    def evaluate(self, batch):
        with torch.no_grad():
            inputs = Variable(batch[0]).float()
            labels = Variable(batch[1]).float()

            inputs, labels = inputs.to(self.device), labels.to(self.device)

            outputs = self.net(inputs)

            loss = self.criterion(torch.cat(outputs), labels)
            accuracy = torch.sum((torch.cat(outputs) > 0) & labels.byte()).float()
            accuracy /= torch.sum((torch.cat(outputs) > 0) | labels.byte()).float()

        return loss.cpu().item(), accuracy.cpu().item(), torch.stack(outputs).cpu().numpy()

    def run_training(self):
        """
        Trains the given neural network
        """
        num_epoch = 1
        num_iter = 1

        validation_split = 0.2
        valid_indexes = self.getTrainer().volume.getValidData()
        random_idx = np.random.permutation(valid_indexes)
        train_idx = random_idx[:int(len(valid_indexes)*(1-validation_split))].copy()
        val_idx = random_idx[int(len(valid_indexes)*validation_split):].copy()

        train_idx = train_idx[:(len(train_idx) - len(train_idx) % 16)]
        train_idx = train_idx.reshape((-1, 16))

        while num_epoch <= self.getTrainer().max_epochs:
            np.random.shuffle(train_idx)
            for i in range(train_idx.shape[0]):
                sample_batch = list(zip(*[self.getTrainer().volume[idx] for idx in train_idx[i]]))
                sample_batch = [np.stack(batch) for batch in sample_batch]
                sample_batch[1] = sample_batch[1] > 0
                if num_epoch > self.getTrainer().max_epochs:
                    break
                if (sample_batch[1] == 0).all():
                    continue

                print("Iteration: {}".format(num_iter))
                self.run_epoch([torch.from_numpy(batch) for batch in sample_batch])

                if num_iter % 10 == 0:
                    val_batch = list(zip(*[self.getTrainer().volume[idx]
                                           for idx in val_idx[:1]]))
                    val_batch = [np.stack(batch) for batch in val_batch]
                    val_batch[1] = val_batch[1] > 0 
                    loss, accuracy, _ = self.evaluate([torch.from_numpy(batch) for batch in val_batch])
                    print("Iteration: {}".format(num_iter),
                          "Epoch {}/{} ".format(num_epoch,
                                                self.getTrainer().max_epochs),
                          "Loss: {:.4f}".format(loss),
                          "Accuracy: {:.2f}".format(accuracy*100))

                num_iter += 1

            num_epoch += 1


class TrainerDecorator(Trainer):
    """
    A wrapper class to a features for training
    """
    def __init__(self, trainer):
        self.setTrainer(trainer)

    def setTrainer(self, trainer):
        self._trainer = trainer

    def getTrainer(self):
        if isinstance(self._trainer, TrainerDecorator) or issubclass(type(self._trainer), TrainerDecorator):
            return self._trainer.getTrainer()
        if isinstance(self._trainer, Trainer):
            return self._trainer

    def run_epoch(self, sample_batch):
        return self._trainer.run_epoch(sample_batch)

    def evaluate(self, batch):
        return self._trainer.evaluate(batch)

    def run_training(self):
        """
        Trains the given neural network
        """
        num_epoch = 1
        num_iter = 1

        validation_split = 0.2
        valid_indexes = self.getTrainer().volume.getVolume().getValidData()
        random_idx = np.random.permutation(valid_indexes)
        train_idx = random_idx[:int(len(valid_indexes)*(1-validation_split))].copy()
        val_idx = random_idx[int(len(valid_indexes)*validation_split):].copy()

        train_idx = train_idx[:(len(train_idx) - len(train_idx) % 8)]
        train_idx = train_idx.reshape((-1, 8))

        while num_epoch <= self.getTrainer().max_epochs:
            np.random.shuffle(train_idx)
            for i in range(train_idx.shape[0]):
                sample_batch = list(zip(*[self.getTrainer().volume[idx] for idx in train_idx[i]]))
                sample_batch = [np.stack(batch) for batch in sample_batch]
                sample_batch[1] = sample_batch[1] > 0
                if num_epoch > self.getTrainer().max_epochs:
                    break

                print("Iteration: {}".format(num_iter))
                self.run_epoch([torch.from_numpy(batch.astype(np.float)) for batch in sample_batch])

                if num_iter % 10 == 0:
                    self.getTrainer().volume.getVolume().setAugmentation(False)
                    val_batch = list(zip(*[self.getTrainer().volume[idx]
                                           for idx in val_idx[:16]]))
                    val_batch = [np.stack(batch) for batch in val_batch]
                    val_batch[1] = val_batch[1] > 0
                    loss, accuracy, _ = self.evaluate([torch.from_numpy(batch.astype(np.float)) for batch in val_batch])
                    print("Iteration: {}".format(num_iter),
                          "Epoch {}/{} ".format(num_epoch,
                                                self.getTrainer().max_epochs),
                          "Loss: {:.4f}".format(loss),
                          "Accuracy: {:.2f}".format(accuracy*100))
                    self.getTrainer().volume.getVolume().setAugmentation(True)

                num_iter += 1

            num_epoch += 1
