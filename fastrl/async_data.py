# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/05b_async_data.ipynb (unless otherwise specified).

__all__ = ['template_data_fit', 'DataFitProcess', 'MultiProcessTfm', 'AsyncExperienceBlock']

# Cell
from fastai.torch_basics import *
from fastai.data.all import *
from fastai.basics import *
import torch.multiprocessing as mp
from .data import *
from .basic_agents import *
from fastcore.all import *
from dataclasses import field,asdict
from typing import List,Any,Dict,Callable
from collections import deque
import gym

if IN_NOTEBOOK:
    from IPython import display
    import PIL.Image

# Cell
def template_data_fit(queue:mp.JoinableQueue=None,items:L=None,agent:BaseAgent=None,learner_cls:Learner=None,experience_block:ExperienceBlock=None,
             cancel:mp.Event=None):
    blk=IterableDataBlock(blocks=(experience_block(agent=agent)),
                          splitter=FuncSplitter(lambda x:False))
    dls=blk.dataloaders(items)
    while True:
        for x in dls[0]:
            queue.put(x)
            if cancel.is_set():
                queue.put(None)
                return None

class DataFitProcess(mp.Process):

    @delegates(template_data_fit,but=['queue','items'])
    def __init__(self,n:int=None,start:bool=False,data_fit=None,**kwargs):
        self.n=n
        super().__init__(target=ifnone(data_fit,template_data_fit),kwargs=kwargs)
        if start:self.start()

    def termijoin(self):
        self.terminate()
        self.join()

# Cell
class MultiProcessTfm(Transform):
    def __init__(self,n:int=1,n_processes:int=1,maxsize:int=1,process_cls=DataFitProcess):
        self.n_processes=n_processes;self.process_cls=process_cls;self.n=n;self.maxsize=maxsize
        self.queue=mp.JoinableQueue(maxsize=maxsize)
        self.cancel=mp.Event()
        self.cached_items=[]

    def setup(self,items:TfmdSource,train_setup=False):
        with items:
            if len(items.items)!=0 and not issubclass(items.items[0].__class__,DataFitProcess):
                self.cached_items=deepcopy(items.items)
            self.reset(items)

    def reset(self,items:TfmdSource,train_setup=False):
        with items:
            self.close(items)
            self.cancel.clear()
            self.queue=mp.JoinableQueue(maxsize=self.maxsize)
            items.items=[self.process_cls(n=self.n,start=True,queue=self.queue,items=self.cached_items,cancel=self.cancel) for _ in range(self.n_processes)]

    def close(self,items:TfmdSource):
        with items:
            self.cancel.set()
            try:
                while not self.queue.empty():self.queue.get()
            except (ConnectionResetError,FileNotFoundError,EOFError,ConnectionRefusedError):pass
            [p.termijoin() for p in items.items if issubclass(p.__class__,DataFitProcess)]
            items.items.clear()

    def encodes(self,o):
        s=self.queue.get()
#         print(s[0])
        return s

# Cell
@delegates(MultiProcessTfm)
def AsyncExperienceBlock(experience_block,agent=None,learner_cls=None,data_fit=None,n_processes=1,n=200,bs=1,**kwargs):
    process_cls=partial(
        DataFitProcess,
        agent=agent,
        learner_cls=learner_cls,
        experience_block=experience_block,
        data_fit=data_fit
    )

    return TransformBlock(type_tfms=[MultiProcessTfm(process_cls=process_cls,n_processes=n_processes,n=n)],dl_type=TfmdSourceDL,
                          dls_kwargs={'bs':bs,'num_workers':0,'verbose':False,'indexed':True,'shuffle_train':False})