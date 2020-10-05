# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/04_learner.ipynb (unless otherwise specified).

__all__ = ['AgentLearner']

# Cell
from fastai.torch_basics import *
from fastai.data.all import *
from fastai.basics import *
from fastai.learner import *
from .basic_agents import *
from dataclasses import field,asdict
from typing import List,Any,Dict,Callable
from collections import deque
import gym

if IN_NOTEBOOK:
    from IPython import display
    import PIL.Image

# Cell
@delegates(Learner)
class AgentLearner(Learner):
    def __init__(self,dls,agent:BaseAgent=BaseAgent(),model=None,use_train_mets=True,**kwargs):
        self.agent=agent
        super().__init__(dls,model=ifnone(model,self.agent.model),**kwargs)
        if use_train_mets:
            for cb in self.cbs:
                if issubclass(cb.__class__,Recorder):cb.train_metrics=True

    def _split(self, b):
        if len(b)==1 and type(b[0])==tuple:b=b[0]
        super()._split(b)

    def predict(self,s):
        return self.agent(s,None)

# Cell
add_docs(AgentLearner,cls_doc="Base Learner for all reinforcement learning agents",
         _split="Since RL environments have primarily 1 source usually, the DL is going to be returning single element tuples (element,)."
                " We want these to be unwrapped properly into a list of elements.",
         predict="The predict method for an `AgentLearner` is mainly feeding into an agent object.")