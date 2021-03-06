# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/20c_qlearning.dqn_target.ipynb (unless otherwise specified).

__all__ = ['TargetDQNTrainer', 'TargetDQNLearner']

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
class TargetDQNTrainer(Callback):
    def __init__(self,n_batch=0): store_attr()
    def after_pred(self):
        exps=[ExperienceFirstLast(*o) for o in self.learn.sample_yb]
        s=torch.stack([e.state for e in exps]).float().to(default_device())
        a=torch.stack([e.action for e in exps]).to(default_device())
        sp=torch.stack([e.last_state for e in exps]).float().to(default_device())
        r=torch.stack([e.reward for e in exps]).float().to(default_device())
        d=torch.stack([e.done for e in exps]).to(default_device())

        state_action_values = self.learn.model(s.float()).gather(1, a.unsqueeze(-1)).squeeze(-1)
#         next_state_values = self.learn.target_model(sp.float()).max(1)[0]
        next_state_values=self.get_next_state_values(sp)
        next_state_values[d] = 0.0

        expected_state_action_values=next_state_values.detach()*(self.learn.discount**self.learn.n_steps)+r
#         print(*self.learn.yb,self.learn.pred)
#         print(self.learn.pred,self.learn.yb)
#         print(self.learn._yb,self.learn.yb[0])
        self.learn._yb=self.learn.yb
        self.learn.yb=(expected_state_action_values.float(),)
#         print(self.learn.yb[0].mean(),self.learn.yb[0].size())
        self.learn.pred=state_action_values
#         print(self.learn.pred.mean(),self.learn.pred.size())

#         print(self.learn.agent.a_selector.epsilon,self.n_batch)

    def get_next_state_values(self,sp):
        return self.learn.target_model(sp.float()).max(1)[0]

#     def after_epoch(self): print(len(self.learn.cbs[4].queue))

    def after_loss(self):
        self.learn.yb=self.learn._yb

    def after_batch(self):
        if self.n_batch%self.learn.target_sync==0:
#             print('copy over',self.n_batch)
            self.learn.target_model.load_state_dict(self.learn.model.state_dict())
        self.n_batch+=1

# Cell
class TargetDQNLearner(AgentLearner):
    def __init__(self,dls,discount=0.99,n_steps=3,target_sync=300,**kwargs):
        store_attr()
        self.target_q_v=[]
        super().__init__(dls,loss_func=nn.MSELoss(),**kwargs)
        self.target_model=deepcopy(self.model)