# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/20b_qlearning.dqn_n_step.ipynb (unless otherwise specified).

__all__ = ['DQNTrainer', 'NStepDQNLearner']

# Cell
import torch.nn.utils as nn_utils
from fastai.torch_basics import *
from fastai.data.all import *
from fastai.basics import *
from dataclasses import field,asdict
from typing import List,Any,Dict,Callable
from collections import deque
import gym
import torch.multiprocessing as mp
from torch.optim import *

from ..data import *
from ..async_data import *
from ..basic_agents import *
from ..learner import *
from ..metrics import *
from ..ptan_extension import *
from .dqn import *

if IN_NOTEBOOK:
    from IPython import display
    import PIL.Image

# Cell
class DQNTrainer(Callback):
    def after_pred(self):
        s,a,r,sp,d,er,steps=(self.learn.xb+self.learn.yb)
        exps=[ExperienceFirstLast(*o) for o in zip(*(self.learn.xb+self.learn.yb))]
        batch_targets=[calc_target(self.learn.model, exp.reward, exp.last_state,exp.done,self.learn.discount**self.learn.n_steps)
                         for exp in exps]

        s_v = s.float()
        q_v = self.learn.model(s_v)
        t_q=q_v.data.numpy().copy()
        t_q[range(len(exps)), a] = batch_targets
        target_q_v = torch.tensor(t_q)
        self.learn._yb=self.learn.yb
        self.learn.yb=(target_q_v,)
        self.learn.pred=q_v
#         print(*self.learn.yb,self.learn.pred)
#         print(self.learn.pred,self.learn.yb)
#         print(self.learn._yb,self.learn.yb[0])

    def after_loss(self):self.learn.yb=self.learn._yb

# Cell
class NStepDQNLearner(AgentLearner):
    def __init__(self,dls,discount=0.99,n_steps=3,**kwargs):
        store_attr()
        self.target_q_v=[]
        super().__init__(dls,loss_func=nn.MSELoss(),**kwargs)