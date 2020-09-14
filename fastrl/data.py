# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/05a_data.ipynb (unless otherwise specified).

__all__ = ['TfmdSourceDL', 'SourceExhausted', 'TfmdSource', 'IterableDataBlock', 'MakeTfm', 'env_display', 'Experience',
           'envlen', 'ResetAndStepTfm', 'ExperienceBlock', 'FirstLastTfm', 'FirstLastExperienceBlock']

# Cell
from fastai.torch_basics import *
from fastai.data.all import *
from fastai.basics import *
from dataclasses import field,asdict
from typing import List,Any,Dict,Callable
from collections import deque
import gym

if IN_NOTEBOOK:
    from IPython import display
    import PIL.Image

# Cell
class TfmdSourceDL(TfmdDL):
    def before_iter(self):
        super().before_iter()
        self.dataset.reset_src()

    def create_item(self,b):
#         print('Before create_item: ',b,self.prebatched)
        b= super().create_item(b)
#         print('After create_item: ',b)
        if type(b)==tuple and len(b)==1 and type(b[0])==tuple: return b[0]
        else:                                                  return b


    def after_iter(self):
        super().after_iter()
        self.dataset.close_src()

# Cell
class SourceExhausted(Exception):pass

@delegates(TfmdLists)
class TfmdSource(TfmdLists):
    "A `Pipeline` of `tfms` applied to a collection of sources called `items`. Only swtches between them if they get exhausted."
    def __init__(self,items, tfms,n:int=None,cycle_srcs=True,verbose=False,**kwargs):
        self.n=n;self.cycle_srcs=cycle_srcs;self.source_idx=0;self.verbose=verbose;self.res_buffer=deque([]);self.extra_len=0
        super().__init__(items,tfms,**kwargs)
#         store_attr('n,cycle_srcs', self) TODO (Josiah): Does not seem to work?

    def __enter__(self):                             self.cycle_srcs=False
    def __exit__(self,exc_type,exc_value,traceback): self.cycle_srcs=True

    def __repr__(self): return f"{self.__class__.__name__}: Cycling sources: {self.cycle_srcs}\n{self.items}\ntfms - {self.tfms.fs}"
    def close_src(self):
        [t.close(self) for t in self.tfms if hasattr(t,'close')]
        self.res_buffer.clear()

    def reset_src(self):
        [t.reset(self) for t in self.tfms if hasattr(t,'reset')]
        self.res_buffer.clear()

    def setup(self,train_setup=True):super().setup(train_setup);self.reset_src()

    def __len__(self):
#         return ifnone(self.n,super().__len__()) TODO (Josiah): self.n is not settable in DataBlock, and since TfmdLists gets reinit, this will not persist
        if len(self.items)!=0 and isinstance(self.items[0],gym.Env) and self.cycle_srcs:
            self.reset_src()
            return self.items[0].spec.max_episode_steps+self.extra_len # TODO(Josiah): This is the only OpenAI dependent code. How do we have htis set in setup?
        if self.n is not None: return self.n
        if len(self.items)!=0 and hasattr(self.items[0],'n'):
            return self.items[0].n # TODO(Josiah): Possible solution to make this more generic?
        return super().__len__()

    def __getitem__(self,idx):
        if len(self.res_buffer)!=0:
#             print('\nBuffer Not Empty:',self.res_buffer)
            return self.res_buffer.popleft()

        try:res=super().__getitem__(self.source_idx if self.cycle_srcs else idx)
        except (IndexError,SourceExhausted) as e:
            if not self.cycle_srcs:raise
            if type(e)==SourceExhausted:
                self.source_idx+=1;  pv(f'SourceExhausted, incrementing to idx {self.source_idx}',verbose=self.verbose)
                if len(self.items)<=self.source_idx:e=IndexError(f'Index {self.source_idx} from SourceExhausted except is out of bounds.')
            if type(e)==IndexError:
                self.source_idx=0;   pv(f'IndexError, setting idx to {self.source_idx}',verbose=self.verbose)
                self.reset_src()
            res=self.__getitem__(self.source_idx)

        if is_listy(res):
            self.res_buffer=deque(res)
#             print('\nBuffer Empty:',self.res_buffer)
            return self.res_buffer.popleft()
        return res

# Cell
class IterableDataBlock(DataBlock):
    tls_type=TfmdSource
    def datasets(self, source, verbose=False):
        self.source = source                     ; pv(f"Collecting items from {source}", verbose)
        items = (self.get_items or noop)(source) ; pv(f"Found {len(items)} items", verbose)
        splits = (self.splitter or RandomSplitter())(items)
        pv(f"{len(splits)} datasets of sizes {','.join([str(len(s)) for s in splits])}", verbose)
        tls=L([self.tls_type(items, t,verbose=verbose) for t in L(ifnone(self._combine_type_tfms(),[None]))])
        return Datasets(items,tls=tls,splits=splits, dl_type=self.dl_type, n_inp=self.n_inp, verbose=verbose)

# Cell
class MakeTfm(Transform):
    def setup(self,items:TfmdSource,train_setup=False):
        with items:
            for i in range(len(items)):items[i]=gym.make(items[i])
        return super().setup(items,train_setup)

# Cell
def env_display(env:gym.Env):
    img=env.render('rgb_array')
    try:display.clear_output(wait=True)
    except AttributeError:pass
    new_im=PIL.Image.fromarray(img)
    display.display(new_im)

# Cell
@dataclass
class Experience():
    d:bool;s:np.ndarray;sp:np.ndarray;r:float;a:Any;eid:int=0;episode_r:float=0;absolute_end:bool=False
def envlen(o:gym.Env):return o.spec.max_episode_steps

@dataclass
class ResetAndStepTfm(Transform):
    def __init__(self,seed:int=None,agent:object=None,n_steps:int=1,steps_delta:int=1,a:Any=None,history:deque=None,
                 s:dict=None,steps:dict=None,maxsteps:int=None,display:bool=False,hist2dict:bool=True):
        self.seed=seed;self.agent=agent;self.n_steps=n_steps;self.steps_delta=steps_delta;self.a=a;self.history=history;self.hist2dict=hist2dict
        self.maxsteps=maxsteps;self.display=display
        self.s=ifnone(s,{})
        self.steps=ifnone(steps,{})
        # store_attr('n,cycle_srcs', self) TODO (Josiah): Does not seem to work?

    def setup(self,items:TfmdSource,train_setup=False):
        self.reset(items)
        self.history=deque(maxlen=self.n_steps)
        return super().setup(items,train_setup)

    def reset(self,items):
        if items.extra_len==0:
            items.extra_len=items.items[0].spec.max_episode_steps*(self.n_steps-1) # Extra steps to unwrap done
        with items:
#         items.cycle_srcs=False
            self.s={id(o):o.reset() for o in items.items if o.seed(self.seed) or True}
            self.steps={id(o):0 for o in items.items}
            self.maxsteps=ifnone(self.maxsteps,envlen(items.items[0]))
            if self.history is not None:self.history.clear()
#         items.cycle_srcs=True

    def queue2dict(self,q:deque):return [asdict(hist) for hist in tuple(copy(q))]
    def encodes(self,o:gym.Env):
        # If history has finished, then instead we try emptying the environment
        if self.history and self.history[-1].d:
            self.history.popleft()
            if len(self.history)==0:raise SourceExhausted
            return self.queue2dict(self.history) if self.hist2dict else copy(self.history)

        while True:
            a=ifnone(self.a,o.action_space.sample()) if self.agent is None else self.agent(self.s[id(o)])[0]
            sp,r,d,_=o.env.step(a)
            if self.display:env_display(o)

            self.steps[id(o)]+=1
            d=self.steps[id(o)]>=self.maxsteps if not d else d

            self.history.append(Experience(d=d,s=self.s[id(o)].copy(),sp=sp.copy(),r=r,a=a,eid=id(o),
                                episode_r=r+(self.history[-1].episode_r if self.history else 0)))
            self.s[id(o)]=sp.copy()

            if self.steps[id(o)]%self.steps_delta!=0: continue # TODO(Josiah): if `steps_delta`!=1, it may skip the first state. Is this ok?
            if len(self.history)!=self.n_steps:       continue
            break

        if len(self.history)==1:self.history[-1].absolute_end=True
        return self.queue2dict(self.history) if self.hist2dict else copy(self.history)

# Cell
@delegates(ResetAndStepTfm)
def ExperienceBlock(dls_kwargs=None,**kwargs):
    return TransformBlock(type_tfms=[MakeTfm(),ResetAndStepTfm(**kwargs)],dl_type=TfmdSourceDL,dls_kwargs=dls_kwargs)

# Cell
class FirstLastTfm(Transform):
    def __init__(self,discount=0.99):self.discount=discount

    def reset(self,items):
        if items.extra_len!=0:items.extra_len=0

    def encodes(self,o):
        total_reward=0.0
        first_o=o[0]
        first_o.sp=o[-1].sp
        for exp in reversed(list(o)):
            total_reward*=self.discount
            total_reward+=exp.r
        first_o.r=total_reward
        return asdict(first_o)


@delegates(ResetAndStepTfm)
def FirstLastExperienceBlock(dls_kwargs=None,**kwargs):
    return TransformBlock(type_tfms=[MakeTfm(),ResetAndStepTfm(hist2dict=False,**kwargs),FirstLastTfm],dl_type=TfmdSourceDL,dls_kwargs=dls_kwargs)