# Electoral System of Ireland: Proportional Representation with Single Transferable Vote (PR-STV)

Ireland uses the **Single Transferable Vote (PR-STV)** for its national parliament (*Dáil Éireann*). It is widely regarded as one of the most "voter-friendly" systems because it allows citizens to rank candidates and ensures that few votes are "wasted."

## 1. Core Mechanics

### The Ballot
Instead of picking one person, voters rank candidates in order of preference:
*   **1** for your first choice.
*   **2** for your second choice.
*   **3** for your third, and so on.

### The Quota (The Winning Post)
To be elected, a candidate must reach a specific number of votes called the **Droop Quota**.
$$ \text{Quota} = \left( \frac{\text{Total Valid Votes}}{\text{Seats} + 1} \right) + 1 $$

### The Counting Process
The count proceeds in rounds:
1.  **First Count:** Only "Number 1" votes are counted. Any candidate reaching the quota is elected.
2.  **Surplus Distribution:** If an elected candidate has *more* votes than the quota, their surplus is transferred to the next available preference on those ballots.
3.  **Elimination:** If no one hits the quota, the candidate with the fewest votes is eliminated. Their ballots are redistributed to the next preferences marked.

---

## 2. Illustrated Example

**Scenario:** A 3-seat constituency with 10,000 valid votes.
**Quota Calculation:** $(10,000 / (3 + 1)) + 1 = \mathbf{2,501}$

| Candidate | Party | Round 1 (1st Prefs) | Result |
| :--- | :--- | :--- | :--- |
| **Alice** | Green | 4,000 | **ELECTED (Round 1)** |
| **Bob** | Blue | 2,000 | Still Running |
| **Charlie** | Red | 1,800 | Still Running |
| **Dana** | Yellow | 1,400 | Still Running |
| **Eve** | Orange | 800 | Still Running |

### Round 2: Distributing Alice's Surplus
Alice has a surplus of **1,499** (4,000 - 2,501). We look at the #2 preferences on her 4,000 ballots.
*   Let's say 80% of Alice's voters picked **Bob** as #2.
*   Bob receives 1,199 extra votes.
*   **Bob's New Total:** 3,199. **BOB IS ELECTED.**

### Round 3: Distributing Bob's Surplus
Bob now has a surplus of **698** (3,199 - 2,501). These are moved to the #3 choices.
*   Most go to **Charlie**. Charlie now has 2,300 votes.

### Round 4: Elimination
No one else has the quota. **Eve** (800) and **Dana** (1,400) are still in. Eve is the lowest, so she is eliminated.
*   Eve's 800 votes are moved to the next available preference. 300 go to **Charlie**.
*   **Charlie's New Total:** 2,600. **CHARLIE IS ELECTED.**

**Final Result:** Alice, Bob, and Charlie take the three seats.

---

## 3. Key Characteristics
*   **Proportionality:** The share of seats usually matches the share of the vote quite closely.
*   **Candidate Choice:** Voters can choose between different candidates from the *same* party.
*   **Complexity:** Counting can take days, as it involves manual handling of physical ballots through multiple rounds.
