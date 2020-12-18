# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/05a_ptan_extend.ipynb (unless otherwise specified).

__all__ = ['Experience', 'ExperienceSource', 'ExperienceFirstLast', 'ExperienceSourceFirstLast']

# Cell
import collections

Experience = collections.namedtuple('Experience', ['state', 'action', 'reward', 'done','episode_reward','steps'])

# Cell
import ptan
import gym
from queue import deque

class ExperienceSource(ptan.experience.ExperienceSource):
    def __init__(self, env, agent, steps_count=2, steps_delta=1, vectorized=False,seed=0):
        """
        Create simple experience source
        :param env: environment or list of environments to be used
        :param agent: callable to convert batch of states into actions to take
        :param steps_count: count of steps to track for every experience chain
        :param steps_delta: how many steps to do between experience items
        :param vectorized: support of vectorized envs from OpenAI universe
        """
        assert isinstance(env, (gym.Env, list, tuple))
        assert isinstance(agent, ptan.agent.BaseAgent)
        assert isinstance(steps_count, int)
        assert steps_count >= 1
        assert isinstance(vectorized, bool)
        if isinstance(env, (list, tuple)):
            self.pool = env
        else:
            self.pool = [env]
        self.agent = agent
        self.steps_count = steps_count
        self.steps_delta = steps_delta
        self.total_rewards = []
        self.total_steps = []
        self.vectorized = vectorized
        self.seed=seed

    def __iter__(self):
        states, agent_states, histories, cur_rewards, cur_steps = [], [], [], [], []
        env_lens = []
        for env in self.pool:
            obs = env.reset()
            env.seed(self.seed)
            # if the environment is vectorized, all it's output is lists of results.
            # Details are here: https://github.com/openai/universe/blob/master/doc/env_semantics.rst
            if self.vectorized:
                obs_len = len(obs)
                states.extend(obs)
            else:
                obs_len = 1
                states.append(obs)
            env_lens.append(obs_len)

            for _ in range(obs_len):
                histories.append(deque(maxlen=self.steps_count))
                cur_rewards.append(0.0)
                cur_steps.append(0)
                agent_states.append(self.agent.initial_state())

        iter_idx = 0
        while True:
            actions = [None] * len(states)
            states_input = []
            states_indices = []
            for idx, state in enumerate(states):
                if state is None:
                    actions[idx] = self.pool[0].action_space.sample()  # assume that all envs are from the same family
                else:
                    states_input.append(state)
                    states_indices.append(idx)
            if states_input:
                states_actions, new_agent_states = self.agent(states_input, agent_states)
                for idx, action in enumerate(states_actions):
                    g_idx = states_indices[idx]
                    actions[g_idx] = action
                    agent_states[g_idx] = new_agent_states[idx]
            grouped_actions = ptan.experience._group_list(actions, env_lens)

            global_ofs = 0
            for env_idx, (env, action_n) in enumerate(zip(self.pool, grouped_actions)):
                if self.vectorized:
                    next_state_n, r_n, is_done_n, _ = env.step(action_n)
                else:
                    next_state, r, is_done, _ = env.step(action_n[0])
                    next_state_n, r_n, is_done_n = [next_state], [r], [is_done]

                for ofs, (action, next_state, r, is_done) in enumerate(zip(action_n, next_state_n, r_n, is_done_n)):
                    idx = global_ofs + ofs
                    state = states[idx]
                    history = histories[idx]

                    cur_rewards[idx] += r
                    cur_steps[idx] += 1
                    if state is not None:
                        history.append(Experience(state=state, action=action, reward=r, done=is_done,steps=cur_steps[idx],episode_reward=cur_rewards[idx]))
                    if len(history) == self.steps_count and iter_idx % self.steps_delta == 0:
                        yield tuple(history)
                    states[idx] = next_state
                    if is_done:
                        # in case of very short episode (shorter than our steps count), send gathered history
                        if 0 < len(history) < self.steps_count:
                            yield tuple(history)
                        # generate tail of history
                        while len(history) > 1:
                            history.popleft()
                            yield tuple(history)
                        self.total_rewards.append(cur_rewards[idx])
                        self.total_steps.append(cur_steps[idx])
                        cur_rewards[idx] = 0.0
                        cur_steps[idx] = 0
                        # vectorized envs are reset automatically
                        states[idx] = env.reset() if not self.vectorized else None
                        agent_states[idx] = self.agent.initial_state()
                        history.clear()
                global_ofs += len(action_n)
            iter_idx += 1

# Cell
ExperienceFirstLast = collections.namedtuple('ExperienceFirstLast', ('state', 'action', 'reward', 'last_state','done','episode_reward','steps'))

# Cell
class ExperienceSourceFirstLast(ExperienceSource):
    def __init__(self, env, agent, gamma, steps_count=1, steps_delta=1, vectorized=False,exclude_nones=False,seed=0):
        assert isinstance(gamma, float)
        super(ExperienceSourceFirstLast, self).__init__(env, agent, steps_count+1, steps_delta, vectorized=vectorized,seed=0)
        self.gamma = gamma
        self.steps = steps_count
        self.exclude_nones=exclude_nones
        if exclude_nones and steps_count==1:
            print('WARNING: steps_count==1 while exclude_nones is True. Setting steps_count==2 to avoid runtime errors.')
            self.steps=2

    def __iter__(self):
        for exp in super(ExperienceSourceFirstLast, self).__iter__():
            if self.exclude_nones:
                if exp[-1].done and len(exp) <= self.steps:

                    if len(exp)==1:continue
                    last_state = exp[-1].state
                    elems = exp
                else:
                    last_state = exp[-1].state
                    elems = exp[:-1]
            else:
                if exp[-1].done and len(exp) <= self.steps:
                    last_state = None
                    elems = exp
                else:
                    last_state = exp[-1].state
                    elems = exp[:-1]
            total_reward = 0.0
            for e in reversed(elems):
                total_reward *= self.gamma
                total_reward += e.reward
            yield ExperienceFirstLast(state=exp[0].state, action=exp[0].action,done=exp[-1].done,
                                      reward=total_reward, last_state=last_state,steps=exp[-1].steps,
                                      episode_reward=exp[-1].episode_reward)