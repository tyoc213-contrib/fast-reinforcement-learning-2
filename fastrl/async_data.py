# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/05c_async_data.ipynb (unless otherwise specified).

__all__ = ['noopo', 'template_data_fit', 'DataFitProcess', 'safe_get', 'MultiProcessTfm', 'TotalReward',
           'AsyncExperienceBlock']

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
import queue
from queue import Empty
import sys
import traceback
from time import sleep

if IN_NOTEBOOK:
    from IPython import display
    import PIL.Image

# Cell
class _noopo():
    def __getattr__(self,*args):       return noopo
    def __call__(self,*args,**kwargs): return noopo
    def __getitem__(self,*args):       return noopo
    def __bool__(self):                return False
noopo = _noopo()

# Cell
def template_data_fit(train_queue=None,items:L=None,
                      agent:BaseAgent=None,experience_block:ExperienceBlock=None,
                      cancel=None):
    sleep(3)
    train_queue=ifnone(train_queue,mp.JoinableQueue)
    cancel=ifnone(cancel,mp.Event)
    ifnone(pipe_out,noopo).send('Hello')
    try:
        blk=IterableDataBlock(blocks=(experience_block(agent=agent())),
                          splitter=FuncSplitter(lambda x:False))
        dls=blk.dataloaders(items,device=get_default_device())
        while True:
            for xb in dls[0]:
                xb=[o.cpu().numpy()[0] for o in xb]
                xb=[ExperienceFirstLast(state=xb[0],action=xb[1],reward=xb[2],
                                        last_state=xb[3], # if not xb[4] else None,
                                        done=xb[4],
                                        episode_reward=xb[5])]

                new_rewards = [o.episode_reward for o in xb if o.done and int(o.episode_reward) != 0]
                if new_rewards: train_queue.put(TotalReward(reward=np.mean(new_rewards)))

                for x in xb: train_queue.put(x)
                if cancel.is_set():
                    train_queue.put(None)
                    return None
    finally:
        cancel.set()

# Cell
class DataFitProcess(mp.Process):
    @delegates(template_data_fit,but=['train_queue','items','pipe_in','pipe_out'])
    def __init__(self,start:bool=False,data_fit=None,**kwargs):
        super().__init__(target=ifnone(data_fit,template_data_fit),kwargs=kwargs)
#         sleep(3)
        if start:
            self.start()
            print('starting')

    def termijoin(self):
        self.terminate()
        self.join()

# Cell
class _LinearA2C(nn.Module):
    def __init__(self, input_shape, n_actions):
        super(_LinearA2C, self).__init__()

        self.policy = nn.Sequential(
            nn.Linear(input_shape[0], 512),
            nn.ReLU(),
            nn.Linear(512, n_actions)
        )
        self.value = nn.Sequential(
            nn.Linear(input_shape[0], 512),
            nn.ReLU(),
            nn.Linear(512, 1)
        )

    def forward(self, x):
        fx=x.float()
        return self.policy(fx),self.value(fx)

# Cell
def safe_get(q,e,p_in):
    while not e.is_set():
        if ifnone(p_in,noopo).poll(): print(p_in.recv())
        try: return q.get_nowait()
        except Empty:pass

# Cell
TotalReward = collections.namedtuple('TotalReward', field_names='reward')

class MultiProcessTfm(Transform):
    def __init__(self,
                 n_processes: int = 1, process_cls=None,
                 cancel=None,
                 verbose: str = False,
                 regular_get: bool = True,
                 tracker=None
                 ):
        store_attr(but='process_cls')
        self.process_cls=ifnone(process_cls,DataFitProcess)
        self.queue = mp.JoinableQueue(maxsize=self.n_processes)
        self.cancel = ifnone(self.cancel,mp.Event())
        self.pipe_in, self.pipe_out = mp.Pipe(False) if self.verbose else (None, None)
        self.cached_items = []
        self._place_holder_out = None
        self.step_idx=0

    def setup(self, items: TfmdSource, train_setup=False):
        pv('setting up',self.verbose)
        self.cancel.clear()
        if len(items.items) != 0 and not issubclass(items.items[0].__class__, DataFitProcess):
            self.cached_items = deepcopy(items.items)
        self.reset(items)

    def reset(self, items: TfmdSource, train_setup=False):
        pv('reset',self.verbose)
        self.step_idx = 0
        self.close(items)
        self.cancel.clear()
        self.queue = mp.JoinableQueue(maxsize=self.n_processes)
        items.items = [self.process_cls(start=True, items=self.cached_items,train_queue=self.queue,cancel=self.cancel)
                       for _ in range(self.n_processes)]
        if not all([p.is_alive() for p in items.items]): raise CancelFitException()

    def close(self, items: TfmdSource):
        self.step_idx = 0
        pv('close',self.verbose)
        self.cancel.set()
        try:
            while not self.queue.empty():o=self.queue.get()
        except (ConnectionResetError, FileNotFoundError, EOFError, ConnectionRefusedError, RuntimeError):
            print('exception? is the queue empty? ',self.queue.empty())
        for o in [p for p in items.items if issubclass(p.__class__, DataFitProcess)]:
            o.termijoin()
            del o
            torch.cuda.empty_cache()
        items.items.clear()

    def encodes(self, o):
        pv('encodes {o}', self.verbose)
        while True:
            if not self.cancel.is_set():
                o=safe_get(self.queue,self.cancel,self.pipe_in) if not self.regular_get else self.queue.get()
                self._place_holder_out = ifnone(self._place_holder_out, o)
                if isinstance(o, TotalReward):
                    if ifnone(self.tracker,noopo()).reward(o.reward, self.step_idx):sys.exit()
                    self.step_idx+=1
                    continue
                return [o]
            else:
                raise CancelFitException()

# Cell
def AsyncExperienceBlock(experience_block, agent=None, data_fit=None, n_processes=1, n=200, bs=1,**kwargs):
    process_cls = partial(
        DataFitProcess,
        agent=agent,
        experience_block=experience_block,
        data_fit=data_fit
    )

    return TransformBlock(type_tfms=[
        MultiProcessTfm(process_cls=process_cls, n_processes=n_processes, **kwargs)],
                          dl_type=TfmdSourceDL, dls_kwargs={'bs': bs, 'num_workers': 0, 'verbose': False, 'indexed': True,
                                      'shuffle_train': False, 'n': n})