# import os
import random
from collections import deque
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.optim as optim
import Utils


def plot_dqn(dqn_rewards):
    plt.figure(figsize=(10, 6))
    plt.plot(dqn_rewards, label="DQN", color="blue")
    plt.xlabel("Deneme Sayısı")
    plt.ylabel("Ödül Değeri")
    plt.title("LunarLander Ortamında DQN-PPO-A3C Algoritma Karşılaştırması")
    plt.legend()
    plt.grid()
    plt.show()

# Define DQN model
class DQNModel(nn.Module):
    def __init__(self, state_size, action_size, hidden_layers=(512, 512)):
        super().__init__()
        layers = []
        input_dim = state_size
        for layer_size in hidden_layers:
            layers.append(nn.Linear(input_dim, layer_size))
            layers.append(nn.ReLU())
            input_dim = layer_size
        layers.append(nn.Linear(input_dim, action_size))
        self.network = nn.Sequential(*layers)

    def forward(self, x):
        return self.network(x)


# Trainer for DQN
class DQNTrainer:
    def __init__(self, env, state_size, action_size, config):
        self.env = env
        self.state_size = state_size
        self.action_size = action_size
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(self.device)
        self.config = config
        self.model = DQNModel(state_size, action_size).to(self.device)
        self.target_model = DQNModel(state_size, action_size).to(self.device)
        self.target_model.load_state_dict(self.model.state_dict())
        self.optimizer = optim.Adam(self.model.parameters(), lr=config['lr'])
        self.memory = deque(maxlen=config.get('memory_size', 10000))
        self.epsilon = config.get('epsilon_start', 1.0)
        self.plot_and_log = Utils.PlotAndLog("DQN")

    def train(self, max_episodes=1000):
        rewards = []

        for episode in range(max_episodes):
            state, _ = self.env.reset()
            state = torch.FloatTensor(state).to(self.device)
            total_reward = 0
            done = False

            while not done:
                action = self._select_action(state)
                next_state, reward, done, truncated, _ = self.env.step(action)
                done = done or truncated
                next_state = torch.FloatTensor(next_state).to(self.device)
                self.memory.append((state, action, reward, next_state, done))
                state = next_state
                total_reward += reward

                if len(self.memory) >= self.config['batch_size']:
                    self._learn()

            self.epsilon = max(
                self.config.get('epsilon_end', 0.01),
                self.epsilon * self.config.get('epsilon_decay', 0.995)
            )

            rewards.append(total_reward)
            # self.plot_and_log.log(episode, total_reward)

            if episode % self.config.get('save_freq', 1000) == 0:
                Utils.save_model(self.model, f"models/dqn/dqn_model_{episode}.pth")

            print(f"Episode {episode}, Reward: {total_reward}")

            if episode % self.config.get('target_update_freq', 10) == 0:
                self.target_model.load_state_dict(self.model.state_dict())

        self.plot_and_log.plot_rewards(rewards)
        return rewards

    def _select_action(self, state):
        if random.random() < self.epsilon:
            return self.env.action_space.sample()
        else:
            with torch.no_grad():
                q_values = self.model(state)
                return torch.argmax(q_values).item()

    def _learn(self):
        batch = random.sample(self.memory, self.config['batch_size'])
        states, actions, rewards, next_states, dones = zip(*batch)

        states = torch.stack(states)
        next_states = torch.stack(next_states)
        rewards = torch.FloatTensor(rewards).to(self.device)
        actions = torch.LongTensor(actions).to(self.device)
        dones = torch.FloatTensor(dones).to(self.device)

        current_q = self.model(states).gather(1, actions.unsqueeze(1)).squeeze(1)
        next_q = self.target_model(next_states).max(1)[0]
        target_q = rewards + self.config['gamma'] * next_q * (1 - dones)

        loss = nn.MSELoss()(current_q, target_q.detach())
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()