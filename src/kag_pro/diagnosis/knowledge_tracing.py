"""Bayesian Knowledge Tracing — track student mastery and question difficulty."""

from collections import defaultdict


class KnowledgeTracer:
    """Bayesian Knowledge Tracing model for tracking student knowledge state.

    Standard BKT with four parameters per skill:
    - p_init:  Probability student already knows the skill before instruction
    - p_learn: Probability student learns the skill from a single practice opportunity
    - p_guess: Probability student guesses correctly when they don't know
    - p_slip:  Probability student slips (makes error) when they do know

    After each answer, updates P(know) using Bayes' theorem.
    """

    def __init__(self, p_init: float = 0.3, p_learn: float = 0.15, p_guess: float = 0.2, p_slip: float = 0.1):
        self.p_init = p_init
        self.p_learn = p_learn
        self.p_guess = p_guess
        self.p_slip = p_slip
        self._knowledge: dict[str, float] = defaultdict(lambda: p_init)
        self._history: list[dict] = []

    def update(self, knowledge_point: str, correct: bool) -> dict:
        """Update knowledge state after observing a correct/incorrect answer.

        Returns: updated state dict with {p_know, predicted_prob, mastery_level}
        """
        p_know = self._knowledge[knowledge_point]

        # Predict probability of correct answer (before observing)
        p_correct = p_know * (1 - self.p_slip) + (1 - p_know) * self.p_guess

        # Update P(know) using Bayes' theorem
        if correct:
            p_know_given_obs = (p_know * (1 - self.p_slip)) / p_correct
        else:
            p_know_given_obs = (p_know * self.p_slip) / (1 - p_correct)

        # Add learning opportunity effect
        p_know_new = p_know_given_obs + (1 - p_know_given_obs) * self.p_learn

        self._knowledge[knowledge_point] = p_know_new

        mastery = self._mastery_level(p_know_new)
        record = {
            "knowledge_point": knowledge_point,
            "correct": correct,
            "p_know_before": round(p_know, 3),
            "p_know_after": round(p_know_new, 3),
            "p_predicted": round(p_correct, 3),
            "mastery": mastery,
        }
        self._history.append(record)
        return record

    def predict(self, knowledge_point: str) -> float:
        """Predict probability of correct answer for a given skill."""
        p_know = self._knowledge[knowledge_point]
        return p_know * (1 - self.p_slip) + (1 - p_know) * self.p_guess

    def get_mastery(self, knowledge_point: str) -> str:
        return self._mastery_level(self._knowledge[knowledge_point])

    def get_all_mastery(self) -> dict[str, dict]:
        return {
            kp: {
                "p_know": round(p, 3),
                "mastery": self._mastery_level(p),
            }
            for kp, p in sorted(self._knowledge.items(), key=lambda x: -x[1])
        }

    def get_weakest(self, n: int = 3) -> list[tuple[str, float]]:
        """Return the n weakest knowledge points."""
        sorted_kp = sorted(self._knowledge.items(), key=lambda x: x[1])
        return [(kp, round(p, 3)) for kp, p in sorted_kp[:n]]

    def get_learning_curve(self, knowledge_point: str) -> list[float]:
        """Extract learning curve for a knowledge point from history."""
        return [
            h["p_know_after"]
            for h in self._history
            if h["knowledge_point"] == knowledge_point
        ]

    @staticmethod
    def _mastery_level(p_know: float) -> str:
        if p_know >= 0.85:
            return "mastered"
        elif p_know >= 0.65:
            return "proficient"
        elif p_know >= 0.40:
            return "developing"
        else:
            return "beginner"


class DifficultyEstimator:
    """Estimate question difficulty based on student performance data."""

    def __init__(self):
        self._attempts: dict[str, list[int]] = defaultdict(list)

    def record(self, question_id: str, correct: bool):
        self._attempts[question_id].append(1 if correct else 0)

    def estimate(self, question_id: str) -> float:
        """Estimate difficulty as 1 - success_rate. Returns 0-1 (higher = harder)."""
        attempts = self._attempts.get(question_id, [])
        if not attempts:
            return 0.5  # Default medium difficulty
        return round(1.0 - sum(attempts) / len(attempts), 3)

    def get_top_hard(self, n: int = 5) -> list[tuple[str, float]]:
        scores = {qid: self.estimate(qid) for qid in self._attempts}
        return sorted(scores.items(), key=lambda x: -x[1])[:n]

    def get_top_easy(self, n: int = 5) -> list[tuple[str, float]]:
        scores = {qid: self.estimate(qid) for qid in self._attempts}
        return sorted(scores.items(), key=lambda x: x[1])[:n]


class DeepKnowledgeTracer:
    """Deep Knowledge Tracing (DKT) — LSTM-based neural model.

    Based on: Piech et al., "Deep Knowledge Tracing", NIPS 2015.
    """

    def __init__(self, hidden_size: int = 32, learning_rate: float = 0.01):
        self.hidden_size = hidden_size
        self.lr = learning_rate
        self._model = None
        self._skill_map: dict = {}
        self._next_id = 0
        self._trained = False

    def _skill_id(self, name: str) -> int:
        if name not in self._skill_map:
            self._skill_map[name] = self._next_id
            self._next_id += 1
        return self._skill_map[name]

    @property
    def num_skills(self) -> int:
        return max(1, self._next_id)

    def fit(self, sequences: list, epochs: int = 20):
        """Train on student interaction sequences."""
        import torch
        import torch.nn as nn

        # Build all skill IDs
        for seq in sequences:
            for skill, _ in seq:
                self._skill_id(skill)

        n_skills = self.num_skills
        input_size = n_skills * 2

        class DKTModel(nn.Module):
            def __init__(self, input_sz, hidden_sz, n_sk):
                super().__init__()
                self.lstm = nn.LSTM(input_sz, hidden_sz, batch_first=True)
                self.fc = nn.Linear(hidden_sz, n_sk)

            def forward(self, x):
                out, _ = self.lstm(x)     # (B, T, H)
                return torch.sigmoid(self.fc(out))  # (B, T, n_skills)

        self._model = DKTModel(input_size, self.hidden_size, n_skills)
        opt = torch.optim.Adam(self._model.parameters(), lr=self.lr)
        loss_fn = nn.BCELoss()

        # Prepare training data
        X_batches, y_batches = [], []
        for seq in sequences:
            if len(seq) < 2:
                continue
            x_seq, y_seq = [], []
            for i in range(len(seq) - 1):
                skill, correct = seq[i]
                sid = self._skill_id(skill)
                in_vec = [0.0] * input_size
                in_vec[sid] = 1.0
                in_vec[n_skills + sid] = float(correct)
                x_seq.append(in_vec)
                # Target: next skill's correctness
                next_skill, next_correct = seq[i + 1]
                next_sid = self._skill_id(next_skill)
                tgt = [0.0] * n_skills
                tgt[next_sid] = float(next_correct)
                y_seq.append(tgt)
            if x_seq:
                X_batches.append(torch.tensor(x_seq, dtype=torch.float32))
                y_batches.append(torch.tensor(y_seq, dtype=torch.float32))

        if not X_batches:
            return

        self._model.train()
        for _epoch in range(epochs):
            total_loss = 0.0
            for X, y in zip(X_batches, y_batches):
                Xb = X.unsqueeze(0)
                yb = y.unsqueeze(0)
                opt.zero_grad()
                preds = self._model(Xb)
                loss = loss_fn(preds.squeeze(0), yb.squeeze(0))
                loss.backward()
                opt.step()
                total_loss += loss.item()

        self._trained = True

    def predict(self, skill_name: str, history: list) -> float:
        """Predict P(correct) for skill given interaction history."""
        if not self._trained or not history:
            return 0.5
        import torch
        self._model.eval()
        n_skills = self.num_skills
        x_seq = []
        for sk, corr in history:
            sid = self._skill_map.get(sk, 0)
            vec = [0.0] * (n_skills * 2)
            vec[sid] = 1.0
            vec[n_skills + sid] = float(corr)
            x_seq.append(vec)
        if not x_seq:
            return 0.5
        X = torch.tensor(x_seq, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            preds = self._model(X)
            target_sid = self._skill_map.get(skill_name, 0)
            return float(preds[0, -1, target_sid].item())

    def get_all_predictions(self, skill_names: list, history: list) -> dict:
        return {sk: self.predict(sk, history) for sk in skill_names}

