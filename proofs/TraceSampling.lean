import Std

/- A small kernel-checked discrete core. This file does NOT formalize the
   continuous probability model, OpenTelemetry, or experimental validity. -/
namespace TraceSampling

def witnesses (keep : Nat → Bool) : List Nat → Nat
  | [] => 0
  | x :: xs => (if keep x then 1 else 0) + witnesses keep xs

theorem witnesses_mono (a b : Nat → Bool)
    (h : ∀ x, a x = true → b x = true) (xs : List Nat) :
    witnesses a xs ≤ witnesses b xs := by
  induction xs with
  | nil => simp [witnesses]
  | cons x xs ih =>
    cases ha : a x <;> cases hb : b x <;> simp_all [witnesses]
    omega

theorem downstream_cannot_repair (up down : Nat → Bool)
    (h : ∀ x, down x = true → up x = true) (xs : List Nat) (k : Nat)
    (recovered : k ≤ witnesses down xs) : k ≤ witnesses up xs :=
  Nat.le_trans recovered (witnesses_mono down up h xs)

theorem singleton_lost (keep : Nat → Bool) (x : Nat) (h : keep x = false) :
    witnesses keep [x] = 0 := by simp [witnesses, h]

/- With c retain outcomes and d discard outcomes per witness, seen c d m
   counts all outcome words in which at least one witness is retained. -/
def seen (c d : Nat) : Nat → Nat
  | 0 => 0
  | n + 1 => c * (c + d)^n + d * seen c d n

theorem seen_partition (c d n : Nat) :
    seen c d n + d^n = (c + d)^n := by
  induction n with
  | zero => simp [seen]
  | succ n ih =>
    calc
      seen c d (n+1) + d^(n+1)
          = c * (c+d)^n + d * seen c d n + d * d^n := by
            simp [seen, Nat.pow_succ, Nat.mul_comm]
      _ = c * (c+d)^n + d * (seen c d n + d^n) := by
            rw [Nat.mul_add]; omega
      _ = c * (c+d)^n + d * (c+d)^n := by rw [ih]
      _ = (c+d) * (c+d)^n := by rw [Nat.add_mul]
      _ = (c+d)^(n+1) := by rw [Nat.pow_succ, Nat.mul_comm]

theorem missed_positive (d n : Nat) (hd : 0 < d) : 0 < d^n := by
  exact Nat.pow_pos hd

theorem positive_discard_has_missed_word (c d n : Nat) (hd : 0 < d) :
    seen c d n < (c+d)^n := by
  have partition := seen_partition c d n
  have positive := missed_positive d n hd
  omega

#print axioms witnesses_mono
#print axioms downstream_cannot_repair
#print axioms singleton_lost
#print axioms seen_partition
#print axioms missed_positive
#print axioms positive_discard_has_missed_word
end TraceSampling
