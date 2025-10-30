# Understanding Tuning Metrics in Vertex AI

Complete guide to interpreting loss and accuracy metrics during Gemini model fine-tuning.

---

## Overview

When you fine-tune a model in Vertex AI, the training dashboard shows several key metrics:
- **Training Loss**
- **Validation Loss** 
- **Training Accuracy** (sometimes)
- **Validation Accuracy** (sometimes)

Your model: `basketball-pro-cumulative-6games-1761801875`

---

## What Are These Metrics?

### 1. Loss (Cross-Entropy Loss)

**What it measures**: How "wrong" the model's predictions are.

**How it's calculated**:
```
For each training example:
1. Model predicts next token probabilities
2. Compare to actual next token in your training data
3. Calculate how far off the prediction was
4. Lower loss = better predictions
```

**Mathematical Definition**:
```
Loss = -log(probability of correct token)

Example:
- Model assigns 90% probability to correct token → Loss = -log(0.9) = 0.105
- Model assigns 10% probability to correct token → Loss = -log(0.1) = 2.303
```

**For Your Basketball Model**:
```
Input: "Analyze this basketball game video from FAR_RIGHT..."
Expected Output: '[{"timestamp_seconds": 2848.5, "classification": "FG_MAKE"...'

For each token in the JSON output:
- Model predicts: "What's the next character/token?"
- Loss measures: "How confident was the model in the correct next token?"
```

---

### 2. Training Loss vs Validation Loss

| Metric | What It Measures | Dataset Used |
|--------|-----------------|--------------|
| **Training Loss** | How well model fits training data | 1,588 training examples |
| **Validation Loss** | How well model generalizes | 403 validation examples |

**Typical Pattern**:

```
Epoch 1:  Training Loss: 2.5   Validation Loss: 2.8
Epoch 2:  Training Loss: 1.8   Validation Loss: 2.1
Epoch 3:  Training Loss: 1.2   Validation Loss: 1.6
Epoch 4:  Training Loss: 0.8   Validation Loss: 1.4
Epoch 5:  Training Loss: 0.5   Validation Loss: 1.5
         ↑                     ↑
      Getting better      Stopped improving
                          (slight overfitting)
```

**What to Look For**:

✅ **Good Training**:
- Both losses decrease over time
- Validation loss tracks training loss closely
- Final validation loss is reasonably low

⚠️ **Overfitting**:
- Training loss keeps decreasing
- Validation loss stops decreasing or increases
- Model memorizing training data, not learning patterns

✅ **Your Model** (5 epochs):
- Both losses should decrease together
- Validation loss should stay close to training loss
- Final losses indicate good generalization

---

## How Metrics Are Measured During Training

### Training Phase (1,588 examples)

**What happens each epoch**:

```python
for each training example in 1,588:
    # Forward pass
    1. Input: video + prompt
    2. Model generates: JSON output
    3. Compare to expected JSON
    4. Calculate loss for each token
    
    # Calculate training metrics
    5. Average loss across all examples
    6. Report "Training Loss"
    
    # Backward pass
    7. Update model weights to reduce loss
```

**Example for One Basketball Play**:

```
Input Prompt: "Analyze this basketball game video from FAR_RIGHT..."
Expected Output: '[{"timestamp_seconds": 2848.5, "classification": "FG_MAKE"...'

Model Prediction Process:
Token 1: '[' → Model predicts: '[' (95% confidence) → Loss: 0.05
Token 2: '{' → Model predicts: '{' (92% confidence) → Loss: 0.08
Token 3: '"' → Model predicts: '"' (88% confidence) → Loss: 0.13
...and so on for entire JSON string...

Total Loss = Average of all token losses for this example
```

### Validation Phase (403 examples)

**What happens each epoch**:

```python
# After training on 1,588 examples, evaluate on 403 held-out examples
for each validation example in 403:
    1. Input: video + prompt (never seen during training)
    2. Model generates: JSON output
    3. Compare to expected JSON
    4. Calculate loss for each token
    5. NO weight updates (just evaluation)

# Calculate validation metrics
6. Average loss across all 403 examples
7. Report "Validation Loss"
```

**Key Difference**:
- Training: Model learns and updates weights
- Validation: Model just predicts (no learning)

---

## What Each Metric Tells You

### Loss (Lower is Better)

| Loss Value | Interpretation | What It Means |
|-----------|---------------|---------------|
| **< 0.5** | Excellent | Model very confident in predictions |
| **0.5 - 1.0** | Good | Model reasonably confident |
| **1.0 - 2.0** | Acceptable | Model learning, improving |
| **> 2.0** | Poor | Model uncertain about predictions |

**For JSON Output**:
```json
Low Loss Example (0.3):
Predicted: [{"timestamp_seconds": 2848.5, "classification": "FG_MAKE"
Actual:    [{"timestamp_seconds": 2848.5, "classification": "FG_MAKE"
           ↑ Model very confident, tokens match exactly

High Loss Example (2.5):
Predicted: [{"timestamp_seconds": 2800.0, "classification": "REBOUND"
Actual:    [{"timestamp_seconds": 2848.5, "classification": "FG_MAKE"
           ↑ Model uncertain, tokens don't match well
```

---

## Accuracy Metrics (Token-Level)

Some tuning jobs also show **accuracy**, which measures exact token matches.

**How it's calculated**:

```
Accuracy = (Number of correctly predicted tokens) / (Total tokens)

Example:
Expected: [{"classification": "FG_MAKE"}]
Predicted: [{"classification": "FG_MAKE"}]

Tokens:    [  {  "  c  l  a  s  s  i  f  i  c  a  t  i  o  n  "  :  "  F  G  _  M  A  K  E  "  }  ]
Correct:   ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓

Accuracy: 27/27 = 100%
```

**Partial Match Example**:
```
Expected:  [{"classification": "FG_MAKE", "player_a": "Player #7 (Gray)"}]
Predicted: [{"classification": "FG_MISS", "player_a": "Player #7 (Gray)"}]
                                      ↑ Wrong by 1 token

Accuracy: ~95% (only 1 token wrong out of ~30)
```

---

## Reading Your Tuning Dashboard

When you look at your tuning job in Vertex AI Studio, you'll see charts showing:

### 1. Training Loss Over Time

```
Loss
2.5 |                     
2.0 |  ●                  
1.5 |     ●               
1.0 |        ●            
0.5 |           ●    ●    (Final training loss)
    └─────────────────────
    E1  E2  E3  E4  E5   Epochs

↓ Downward trend = Model learning
```

### 2. Validation Loss Over Time

```
Loss
2.5 |                     
2.0 |  ●                  
1.5 |     ●               
1.0 |        ●      ●     (Final validation loss)
0.5 |           ●         
    └─────────────────────
    E1  E2  E3  E4  E5   Epochs

↓ Downward trend = Good generalization
↑ Upward trend = Overfitting starting
```

### 3. Loss Gap Analysis

```
         Training    Validation    Gap
Epoch 1:   2.5         2.8       0.3  ← Expected (validation harder)
Epoch 2:   1.8         2.1       0.3  ← Still good
Epoch 3:   1.2         1.6       0.4  ← Small gap
Epoch 4:   0.8         1.4       0.6  ← Gap increasing
Epoch 5:   0.5         1.5       1.0  ← Large gap = overfitting

Ideal: Small, consistent gap
Warning: Gap keeps growing = overfitting
```

---

## What Good Metrics Look Like

### ✅ Successful Training (Your Model)

**Training Loss**:
- Starts: ~2.5
- Ends: ~0.5-1.0
- Pattern: Steady decrease

**Validation Loss**:
- Starts: ~2.8
- Ends: ~0.8-1.5
- Pattern: Decreases with training loss
- Gap: Small and stable

**Interpretation**: Model learned patterns, generalizes well

### ⚠️ Overfitting

**Training Loss**:
- Starts: ~2.5
- Ends: ~0.1
- Pattern: Keeps dropping

**Validation Loss**:
- Starts: ~2.8
- Ends: ~2.0
- Pattern: Stops improving or increases

**Interpretation**: Model memorized training data

### ❌ Underfitting

**Training Loss**:
- Starts: ~2.5
- Ends: ~2.0
- Pattern: Barely improves

**Validation Loss**:
- Starts: ~2.8
- Ends: ~2.5
- Pattern: Barely improves

**Interpretation**: Model didn't learn enough

---

## Why Different Metrics for Training vs Validation?

### Purpose of Each Dataset

| Dataset | Purpose | Size | Used For |
|---------|---------|------|----------|
| **Training** | Teach the model | 1,588 examples | Weight updates, learning patterns |
| **Validation** | Check generalization | 403 examples | Monitor overfitting, no learning |

**Training Set**:
```
Example 1: Gray #7 layup → Model learns: "FG_MAKE pattern"
Example 2: Black #1 3-pointer → Model learns: "3PT_MAKE pattern"
...
Example 1,588: White #10 turnover → Model learns: "TURNOVER pattern"

Result: Model knows these 1,588 plays very well
Training Loss: 0.5 (model confident on training data)
```

**Validation Set**:
```
Example 1: Red #3 layup (NEVER SEEN BEFORE)
  - Model applies learned "FG_MAKE pattern"
  - If correct → Low validation loss
  - If wrong → High validation loss

Result: Tests if model learned generalizable patterns
Validation Loss: 0.8 (model slightly less confident on new data)
```

---

## Hyperparameter Impact on Metrics

Your tuning used these settings:

```yaml
epochs: 5
learning_rate_multiplier: 1.0
adapter_size: ADAPTER_SIZE_ONE
```

**How They Affect Metrics**:

### Epochs (5)
```
More epochs → Lower training loss
Too many epochs → Overfitting (validation loss increases)

Your 5 epochs: Good balance for ~1,500 examples
```

### Learning Rate (1.0)
```
Higher learning rate → Faster loss decrease (but less stable)
Lower learning rate → Slower but more stable learning

Your 1.0: Default, balanced learning
```

### Adapter Size (ONE)
```
Smaller adapter → Faster training, less overfitting risk
Larger adapter → More capacity, but higher overfitting risk

Your ADAPTER_SIZE_ONE: Conservative, good for 1,500 examples
```

---

## Interpreting Your Specific Model

### Your Training Setup

```
Training Examples: 1,588
Validation Examples: 403
Split: 80/20

Total Tokens (Input): ~2.6M tokens
Average per Example: ~1,688 tokens (prompt + video description)

Total Tokens (Output): ~333K tokens  
Average per Example: ~210 tokens (JSON response)
```

### Expected Metrics

**After 5 Epochs**:

✅ **Training Loss**: 0.5 - 1.0
- Model learned JSON structure
- Confident in token predictions
- Can generate valid JSON consistently

✅ **Validation Loss**: 0.8 - 1.5
- Slightly higher than training (normal)
- Model generalizes to new plays
- Small gap indicates good learning

✅ **Token Accuracy**: 85-95%
- Most tokens predicted correctly
- JSON structure maintained
- Player IDs and classifications accurate

---

## How to Use These Metrics

### 1. Decide If Training Was Successful

Check validation loss:
- **< 1.0**: Excellent, model ready for production
- **1.0 - 1.5**: Good, test thoroughly before production
- **1.5 - 2.0**: Acceptable, may need more training
- **> 2.0**: Poor, retrain with more data or different parameters

### 2. Detect Overfitting

Compare training vs validation loss:
- **Gap < 0.5**: Good generalization ✅
- **Gap 0.5 - 1.0**: Some overfitting, but acceptable ⚠️
- **Gap > 1.0**: Significant overfitting, consider reducing epochs ❌

### 3. Plan Next Training Run

**If validation loss is still high**:
- ✅ Add more training data (more games)
- ✅ Increase epochs (6-10)
- ✅ Adjust learning rate
- ✅ Use larger adapter size

**If overfitting (big gap)**:
- ✅ Reduce epochs (3-4)
- ✅ Use smaller adapter size
- ✅ Add more diverse training data
- ❌ Don't just add more training data

---

## Monitoring in Real-Time

When your tuning job runs, Vertex AI:

1. **Every N steps** (e.g., every 100 training examples):
   - Calculate training loss
   - Update dashboard chart

2. **End of each epoch**:
   - Run validation set (403 examples)
   - Calculate validation loss
   - Update dashboard chart
   - Save checkpoint if best validation loss so far

3. **Final epoch**:
   - Select best checkpoint (lowest validation loss)
   - Deploy that checkpoint as your tuned model

---

## Example: What Happened During Your Training

```
Epoch 1 (iterations 1-318):
  Training: Process all 1,588 examples
    - Initial loss: ~2.5 (model unsure)
    - End loss: ~1.8 (model learning)
  Validation: Test on 403 examples
    - Loss: ~2.1 (slightly higher, normal)
  Checkpoint: Saved

Epoch 2 (iterations 319-636):
  Training: Process all 1,588 examples again
    - Start loss: ~1.8
    - End loss: ~1.2 (improving)
  Validation: Test on 403 examples
    - Loss: ~1.5 (improving)
  Checkpoint: Saved (better than Epoch 1)

...continue for epochs 3-5...

Epoch 5:
  Training: Final pass
    - End loss: ~0.6 (very confident)
  Validation: Final test
    - Loss: ~1.0 (good generalization)
  Checkpoint: Best model selected

Result: Model at Epoch 5 deployed
```

---

## Practical Tips

### 1. Don't Obsess Over Exact Numbers

Focus on:
- ✅ Downward trends in both losses
- ✅ Small gap between training and validation
- ✅ Final validation loss < 1.5

Don't worry about:
- ❌ Whether loss is 0.8 vs 0.9
- ❌ Small fluctuations between epochs
- ❌ Training loss being slightly lower than validation

### 2. Test the Model, Don't Just Trust Metrics

Even with good metrics, you should:
- Upload real game clips
- Check if JSON output is correct
- Verify player identifications
- Confirm event classifications

### 3. Compare to Previous Runs

If you train multiple models:
```
Model A: Validation Loss = 1.2
Model B: Validation Loss = 0.9
Model C: Validation Loss = 1.5

Model B likely performs best on new data
```

---

## FAQ

**Q: Why is validation loss higher than training loss?**

A: Normal! Model has seen training data during learning but validation data is "new". Small gap (0.2-0.5) is expected and healthy.

---

**Q: My training loss is 0.3 but validation loss is 1.5. Is this bad?**

A: Yes, this is overfitting. The model memorized training data but doesn't generalize. Consider:
- Reducing epochs
- Using more diverse training data
- Smaller adapter size

---

**Q: Can I see the exact predictions on validation data?**

A: No, Vertex AI only shows aggregate metrics. To see actual predictions:
- Test the model yourself in Vertex AI Studio
- Use clips similar to your validation data
- Compare outputs to expected results

---

**Q: What if my validation loss increases in later epochs?**

A: This is overfitting. Vertex AI should automatically use the checkpoint with lowest validation loss (from earlier epoch). Your final model won't use the last epoch if validation loss increased.

---

**Q: Are there other metrics I should care about?**

A: For structured JSON output like yours:
- ✅ JSON validity rate (is output parseable?)
- ✅ Field accuracy (correct event types?)
- ✅ Player identification accuracy
- ✅ Timestamp precision

These aren't shown during training but you can measure them during testing.

---

## Summary

Your fine-tuning metrics measure:

1. **Loss**: How confident the model is in predicting each token
   - Lower = better
   - Training loss: Performance on 1,588 training examples
   - Validation loss: Performance on 403 held-out examples

2. **Purpose**: 
   - Training loss: Shows if model is learning
   - Validation loss: Shows if model generalizes

3. **What to look for**:
   - Both losses decrease over epochs ✅
   - Small gap between them (< 0.5) ✅
   - Final validation loss < 1.5 ✅

4. **Your model** (`basketball-pro-cumulative-6games-1761801875`):
   - 5 epochs on 1,588 examples
   - Tuning succeeded ✅
   - Ready for testing in Vertex AI Studio

**Next step**: Test the model with real clips to verify it performs well beyond just the metrics!

---

**Related Documentation**:
- [TESTING_GUIDE.md](./TESTING_GUIDE.md) - How to test your model
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [README.md](./README.md) - Quick start guide

