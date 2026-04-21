import numpy as np
import xgboost as xgb
from typing import List, Dict, Any, Tuple
import random

# --- 1. Adaptive Neuro-Fuzzy Inference System (ANFIS) - Jang 1991 ---
class ANFIS:
    def __init__(self, n_inputs: int, n_rules: int):
        self.n_inputs = n_inputs
        self.n_rules = n_rules
        # Premise parameters (Gaussian membership: mean and sigma)
        self.premise_params = np.random.randn(n_inputs, n_rules, 2) 
        # Consequent parameters (Linear: y = p*x + q)
        self.consequent_params = np.random.randn(n_rules, n_inputs + 1)

    def gaussian_mf(self, x, mean, sigma):
        return np.exp(-((x - mean)**2) / (2 * (sigma**2) + 1e-9))

    def forward(self, inputs: np.ndarray) -> float:
        # Layer 1: Fuzzification
        w = np.ones(self.n_rules)
        for i in range(self.n_rules):
            for j in range(self.n_inputs):
                w[i] *= self.gaussian_mf(inputs[j], self.premise_params[j, i, 0], self.premise_params[j, i, 1])
        
        # Layer 2 & 3: Rule strength & Normalization
        sum_w = np.sum(w) + 1e-9
        w_norm = w / sum_w
        
        # Layer 4: Defuzzification (Linear combinations)
        layer4_out = np.zeros(self.n_rules)
        for i in range(self.n_rules):
            layer4_out[i] = np.dot(self.consequent_params[i, :-1], inputs) + self.consequent_params[i, -1]
            
        # Layer 5: Final Output
        return float(np.sum(w_norm * layer4_out))

# --- 2. EE-Bat Algorithm (Enhanced Exploration Bat Algorithm) ---
class EEBatOptimizer:
    def __init__(self, objective_func, n_params: int, n_bats=20, n_gen=50):
        self.obj_func = objective_func
        self.n_params = n_params
        self.n_bats = n_bats
        self.n_gen = n_gen
        
        self.f_min = 0
        self.f_max = 2
        self.A = 0.5 # Loudness
        self.r = 0.5 # Pulse rate
        
        # Initialize bats
        self.positions = np.random.uniform(-1, 1, (n_bats, n_params))
        self.velocities = np.zeros((n_bats, n_params))
        self.fitness = np.array([self.obj_func(p) for p in self.positions])
        
        self.best_idx = np.argmin(self.fitness)
        self.best_pos = self.positions[self.best_idx].copy()
        self.best_fitness = self.fitness[self.best_idx]

    def optimize(self):
        for t in range(self.n_gen):
            for i in range(self.n_bats):
                # Update frequency, velocity, position
                freq = self.f_min + (self.f_max - self.f_min) * random.random()
                self.velocities[i] += (self.positions[i] - self.best_pos) * freq
                new_pos = self.positions[i] + self.velocities[i]
                
                # EE modification: Enhanced Local Search
                if random.random() > self.r:
                    new_pos = self.best_pos + 0.01 * np.random.randn(self.n_params)
                
                # Evaluate
                new_fit = self.obj_func(new_pos)
                
                # Acceptance with Loudness
                if new_fit < self.fitness[i] and random.random() < self.A:
                    self.positions[i] = new_pos
                    self.fitness[i] = new_fit
                    
                    # Update best
                    if new_fit < self.best_fitness:
                        self.best_pos = new_pos.copy()
                        self.best_fitness = new_fit
            
            # Update A and r (Loudness decays, Pulse rate increases)
            self.A *= 0.95
            self.r = self.r * (1 - np.exp(-0.1 * t))
            
        return self.best_pos

# --- 3. XGBoost Intent Classifier Wrapper ---
class IntentClassifier:
    def __init__(self):
        self.model = None
        self.categories = ["SALARY", "BUSINESS", "AGRI", "CAPITAL_GAINS", "DEDUCTION_80C", "DEDUCTION_80D", "DEDUCTION_OTHER"]
        
    def mock_train(self):
        # In a real scenario, we'd have a dataset. 
        # Here we simulate a trained XGBoost model for intent detection
        pass

    def predict(self, features: np.ndarray) -> str:
        # For demonstration, we'll use a simplified mapping that mimics XGBoost decision logic
        # High weights for specific keywords in the feature vector
        idx = np.argmax(features)
        return self.categories[idx % len(self.categories)]

# --- 4. LSTM-style Context Manager ---
class ConversationContext:
    def __init__(self):
        self.history = []
        self.profile = {}
        self.hidden_state = np.zeros(64) # Simulated LSTM hidden state

    def update(self, user_msg: str, ai_msg: str):
        self.history.append({"user": user_msg, "ai": ai_msg})
        # Simple "cell state" update based on message length and keywords
        self.hidden_state += (len(user_msg) * 0.01)
        if "don't" in user_msg.lower():
            self.hidden_state *= 0.9 # Forgetting factor
