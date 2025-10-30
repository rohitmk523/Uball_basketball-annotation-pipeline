# Testing Fine-Tuned Models in Vertex AI Studio

Complete guide for testing your basketball play analysis model in the Vertex AI Studio UI.

---

## Table of Contents

1. [Accessing Your Fine-Tuned Model](#accessing-your-fine-tuned-model)
2. [Understanding the Studio Interface](#understanding-the-studio-interface)
3. [Testing with Video Clips](#testing-with-video-clips)
4. [Interpreting Results](#interpreting-results)
5. [Best Practices](#best-practices)
6. [Troubleshooting](#troubleshooting)

---

## Accessing Your Fine-Tuned Model

### Step 1: Navigate to Vertex AI Studio

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project: `refined-circuit-474617-s8`
3. Navigate to **Vertex AI** → **Model Garden** → **Tuning**
4. Find your model: `basketball-pro-cumulative-6games-1761801875`
5. Click **"Test"** or **"Open in Studio"**

### Step 2: Verify Model Selection

In the Studio interface, confirm:
- **Model settings** dropdown shows your tuned model
- Model name: `basketball-pro-cumulative-6games-1761801...`
- Status: Should show as deployed and ready

---

## Understanding the Studio Interface

The new Vertex AI Studio interface consists of several key sections:

### 1. Top Bar
- **Preview/Code Toggle**: Switch between UI testing and code generation
- **Share**: Share your prompt configuration
- **More Options**: Additional settings and actions

### 2. Model Settings
- **Model Selection**: Choose your fine-tuned model
- **Model Parameters**: 
  - Temperature (0.0 - 2.0)
  - Top-P
  - Top-K
  - Max output tokens
  - Stop sequences

### 3. System Instructions

⚠️ **IMPORTANT**: Your model was trained with a **specific prompt format**. For best results, use system instructions that match your training data.

**Your Model's Training Format** (Use this!):
```
You are a basketball play analyzer. Your job is to analyze video clips 
and return structured JSON data about basketball plays.

For each play, identify:
1. timestamp_seconds: When the play occurs
2. classification: Event type (FG_MAKE, FG_MISS, 3PT_MAKE, 3PT_MISS, 
   FREE_THROW_MAKE, FREE_THROW_MISS, REBOUND, ASSIST, STEAL, BLOCK, 
   TURNOVER, FOUL, TIMEOUT, SUB)
3. note: Detailed description of what happened
4. player_a: Primary player (format: "Player #X (Color Team)")
5. player_b: Secondary player if applicable
6. events: Array of all events in the play

Return response as a JSON array.
```

**Alternative (For Natural Language Responses)**:
```
You are an expert basketball analyst. Analyze plays and provide 
detailed, natural language descriptions of:
- Player movements and positioning
- Offensive and defensive strategies
- Key moments and tactical decisions

Note: This may produce less consistent results than the JSON format 
your model was trained on.
```

### 4. Prompt Input Area
- Main area where you compose your prompts
- Supports:
  - Text input
  - File uploads (videos, images)
  - Multiple media items
  - Formatted text

### 5. Tools Panel (Bottom Left)
- **+ (Add)**: Add files or context
- **🔧 Tools**: Enable function calling
- **? Ask**: Get help with prompting
- **Token Counter**: Shows token usage

---

## Testing with Video Clips

### Method 1: Upload Video Files

#### Step 1: Add Video Clip

1. Click the **"+" button** in the prompt input area
2. Select **"Upload file"**
3. Choose a clip from your training data:
   - Location: `gs://uball-training-data/games/{game_id}/clips/`
   - Example: `{play_id}_broadcast.mp4` or `{play_id}_tactical.mp4`
4. Wait for upload to complete

#### Step 2: Add Text Prompt

After uploading the video, add your prompt:

```
Analyze this basketball play in detail. Describe:
1. The offensive strategy being executed
2. Key player movements and positioning
3. Defensive response and coverage
4. The outcome and effectiveness of the play
5. Any tactical insights or notable moments
```

#### Step 3: Run the Test

1. Click **"Submit"** or press `Enter`
2. Wait for the model to process (10-30 seconds for video)
3. Review the generated analysis

### Method 2: Reference GCS Videos

Instead of uploading, you can reference videos directly from GCS:

```
Analyze the basketball play in this video:
gs://uball-training-data/games/23135de8-36ca-4882-bdf1-8796cd8caa8a/clips/abc123_broadcast.mp4

Provide a detailed tactical breakdown.
```

### Method 3: Use Multiple Angles

Test with both broadcast and tactical angles:

```
Compare these two views of the same play:

Broadcast view: [upload broadcast clip]
Tactical view: [upload tactical clip]

Analyze what additional insights the tactical view provides 
compared to the broadcast view.
```

---

## Prompt Templates for Testing

⚠️ **CRITICAL**: Your model was trained to expect a **specific prompt format**. Use these exact templates for best results!

### 1. Exact Training Format (Recommended) ✅

**For Broadcast/Wide Angle Clips:**
```
Analyze this basketball game video from FAR_RIGHT camera angle and identify the play with its events.

This is a FAR_RIGHT camera view that provides wide court view and team formation context.

For the play, provide:
1. timestamp_seconds: The time in the video when the play occurs (number)
2. classification: The primary event type (FG_MAKE, FG_MISS, 3PT_MAKE, 3PT_MISS, FREE_THROW_MAKE, FREE_THROW_MISS, REBOUND, ASSIST, STEAL, BLOCK, TURNOVER, FOUL, TIMEOUT, SUB)
3. note: A detailed description of what happened (string)
4. player_a: The primary player involved (format: "Player #X (Color Team)")
5. player_b: Secondary player if applicable (format: "Player #X (Color Team)")
6. events: Array of all events in the play, each with:
   - label: Event type (same options as classification)
   - playerA: Player identifier (format: "Player #X (Color Team)")
   - playerB: Secondary player if applicable

Return a JSON array with the single play. Be precise with timestamps and identify all basketball events.

[attach video clip]
```

**For Tactical/Close-up Angle Clips:**
```
Analyze this basketball game video from NEAR_LEFT camera angle and identify the play with its events.

This is a NEAR_LEFT camera view that provides close-up details of player numbers and jerseys.

For the play, provide:
1. timestamp_seconds: The time in the video when the play occurs (number)
2. classification: The primary event type (FG_MAKE, FG_MISS, 3PT_MAKE, 3PT_MISS, FREE_THROW_MAKE, FREE_THROW_MISS, REBOUND, ASSIST, STEAL, BLOCK, TURNOVER, FOUL, TIMEOUT, SUB)
3. note: A detailed description of what happened (string)
4. player_a: The primary player involved (format: "Player #X (Color Team)")
5. player_b: Secondary player if applicable (format: "Player #X (Color Team)")
6. events: Array of all events in the play, each with:
   - label: Event type (same options as classification)
   - playerA: Player identifier (format: "Player #X (Color Team)")
   - playerB: Secondary player if applicable

Return a JSON array with the single play. Be precise with timestamps and identify all basketball events.

[attach video clip]
```

### 2. Simplified Format (If You Want Natural Language)

**Basic Play Analysis:**
```
Analyze this basketball play. Describe:
- What type of play it is (shot, turnover, etc.)
- Which players are involved
- What happened step by step

[attach video clip]
```

**Note**: The simplified format may produce less accurate results since the model was trained on structured JSON output.

---

## Interpreting Results

### Expected Output Format

Your model was trained to return **structured JSON**. Here's what to expect:

**Example Output:**
```json
[{
  "timestamp_seconds": 2848.5,
  "classification": "FG_MAKE",
  "note": "Gray #7 made a layup.",
  "player_a": "Player #7 (Gray)",
  "player_b": null,
  "events": [{
    "label": "FG_MAKE",
    "playerA": "Player #7 (Gray)",
    "playerB": null,
    "playerAId": "0210b121-a6d9-4261-b184-abb11f84301c",
    "playerBId": null
  }]
}]
```

**For Complex Plays:**
```json
[{
  "timestamp_seconds": 668.8,
  "classification": "3PT_MISS",
  "note": "Player #1 (Black) missed a 3-pointer, and G5 rebounded.",
  "player_a": "Player #1 (Black)",
  "player_b": null,
  "events": [
    {
      "label": "3PT_MISS",
      "playerA": "Player #1 (Black)",
      "playerB": null,
      "playerAId": "989ec7b2-9452-4d3a-9dcf-b62ea45d165e",
      "playerBId": null
    },
    {
      "label": "REBOUND",
      "playerA": null,
      "playerB": null,
      "playerAId": null,
      "playerBId": null
    }
  ]
}]
```

### What to Look For

**1. Accuracy**
- Does the model correctly identify the play type?
- Are player numbers and team colors correct?
- Is the event classification accurate (FG_MAKE vs 3PT_MAKE)?
- Are timestamps reasonable?

**2. JSON Structure**
- Is the output valid JSON?
- Are all required fields present?
- Is the format consistent with training data?

**3. Event Completeness**
- Are all events in the play captured?
- Is the primary event correctly classified?
- Are secondary events (rebounds, assists) included?

**4. Consistency**
- Test the same clip multiple times
- JSON structure should be identical
- Classifications should not change
- Note descriptions may vary slightly

**5. Comparison to Ground Truth**
- Compare to your training data descriptions
- Check if player identification matches
- Verify event classifications

### Evaluating Model Performance

Create a testing checklist:

```markdown
## Test Result Evaluation

**Clip**: [clip_id]
**Angle**: Broadcast / Tactical
**Play Type**: [actual play type]

### Accuracy (1-5)
- [ ] Play identification: ___/5
- [ ] Player movements: ___/5
- [ ] Tactical analysis: ___/5
- [ ] Outcome description: ___/5

### Quality (1-5)
- [ ] Detail level: ___/5
- [ ] Technical terminology: ___/5
- [ ] Coherence: ___/5
- [ ] Usefulness: ___/5

### Notes:
[Any observations or issues]
```

---

## Best Practices

### 1. Systematic Testing

Test across different categories:

- **Play Types**: 
  - Pick and roll
  - Isolation
  - Fast break
  - Half-court sets
  - Out-of-bounds plays

- **Angles**:
  - Broadcast view
  - Tactical view
  - Both angles together

- **Game Situations**:
  - Early game
  - Close game
  - Blowout
  - End-of-quarter

### 2. Prompt Engineering

**Be Specific**:
```
❌ "Analyze this play."

✅ "Analyze this pick and roll play. Focus on the screen setter's 
positioning, the ball handler's decision-making, and how the 
defense responds to the action."
```

**Provide Context**:
```
This is a late-game situation with 30 seconds left and the team 
down by 2 points. Analyze the play execution and decision-making.

[attach video]
```

**Ask for Structure**:
```
Analyze this play using the following structure:
1. Initial setup and positioning
2. Primary action
3. Defensive response
4. Secondary action or adjustment
5. Outcome and evaluation

[attach video]
```

### 3. Iterative Refinement

1. **Start Simple**: Begin with basic analysis prompts
2. **Add Detail**: Gradually increase complexity
3. **Test Variations**: Try different phrasings
4. **Track Results**: Keep notes on what works best

### 4. Batch Testing

Test multiple clips in sequence:

```
I will show you 3 plays. Analyze each one separately:

Play 1: [upload clip 1]
Play 2: [upload clip 2]
Play 3: [upload clip 3]

For each, describe the offensive strategy and defensive response.
```

---

## Advanced Features

### 1. System Instructions

Use system instructions to set consistent behavior:

```
You are a professional basketball analyst. Always structure your 
analysis in the following format:

**Play Overview**: Brief summary
**Offensive Strategy**: Detailed breakdown
**Defensive Response**: Coverage and adjustments
**Key Moments**: Critical decisions or plays
**Evaluation**: Effectiveness rating (1-10) with justification

Use technical basketball terminology and reference specific 
positions by number when possible.
```

### 2. Few-Shot Examples

Include example analyses in your prompt:

```
Example analysis format:

[Example play description from your training data]

Now analyze this new play:
[attach video]
```

### 3. Multi-Turn Conversations

Build on previous responses:

```
Turn 1: "Analyze this play."
[Model responds]

Turn 2: "Now focus specifically on the help defense rotation."
[Model provides detailed focus]

Turn 3: "What could the offense have done differently?"
[Model suggests alternatives]
```

---

## Model Parameters Guide

### Temperature (0.0 - 2.0)

- **0.0 - 0.3**: Very focused, deterministic responses
  - Use for: Factual analysis, consistent descriptions
  - Best for: Production use

- **0.4 - 0.7**: Balanced creativity and consistency
  - Use for: General analysis
  - Best for: Most use cases

- **0.8 - 1.0**: More creative, varied responses
  - Use for: Alternative perspectives
  - Best for: Brainstorming

- **1.1 - 2.0**: Highly creative, less predictable
  - Use for: Exploration
  - Best for: Testing boundaries

**Recommended for Basketball Analysis**: 0.3 - 0.5

### Top-P (0.0 - 1.0)

Controls diversity of word selection.

- **0.9**: Recommended default
- **0.95**: Slightly more diverse
- **0.8**: More focused

### Top-K (1 - 40)

Limits vocabulary selection.

- **40**: Default, good balance
- **10-20**: More focused
- **1**: Deterministic (like temperature 0)

### Max Output Tokens

- **Default**: 8192
- **Short Analysis**: 512 - 1024
- **Detailed Analysis**: 2048 - 4096
- **Comprehensive Report**: 4096 - 8192

---

## Troubleshooting

### Issue: Model Not Found

**Symptoms**: Can't see your fine-tuned model in the dropdown

**Solutions**:
1. Verify tuning job completed successfully
2. Check you're in the correct project
3. Refresh the page
4. Clear browser cache
5. Verify model is deployed (check Vertex AI → Model Registry)

### Issue: Video Upload Fails

**Symptoms**: Upload doesn't complete or shows error

**Solutions**:
1. Check file size (max ~20MB for UI uploads)
2. Verify video format (MP4 recommended)
3. Try referencing GCS path instead
4. Check IAM permissions for GCS bucket
5. Use shorter clips (< 30 seconds recommended)

### Issue: Slow Response Time

**Symptoms**: Takes >1 minute to get response

**Solutions**:
1. Reduce video length
2. Lower max output tokens
3. Use shorter prompts
4. Check if model is properly deployed
5. Try during off-peak hours

### Issue: Poor Quality Responses

**Symptoms**: Analysis doesn't match training quality

**Solutions**:
1. **Check prompt clarity**: Be more specific
2. **Add system instructions**: Provide context
3. **Adjust temperature**: Try 0.3-0.5
4. **Include examples**: Show desired format
5. **Verify model**: Ensure using the right tuned model

### Issue: Inconsistent Results

**Symptoms**: Same clip produces very different analyses

**Solutions**:
1. Lower temperature (to 0.2-0.3)
2. Reduce top-p (to 0.8)
3. Use more specific prompts
4. Add structured output requirements

---

## Saving and Sharing Results

### Export Prompt

1. Click the **Share** button (top right)
2. Select **"Copy link"** or **"Export as code"**
3. Save for later use or share with team

### Save Configurations

1. Name your prompt in the title field
2. Click the save icon
3. Access saved prompts from the sidebar

### Generate Code

1. Switch to **"Code"** tab
2. Select language (Python, Node.js, curl)
3. Copy code for API integration
4. Use in production applications

---

## Next Steps

### 1. Systematic Evaluation

Create a test suite:
- 10-20 representative clips
- Cover all play types
- Include edge cases
- Document expected outputs

### 2. Benchmark Performance

Compare to:
- Human analyst descriptions
- Original training data quality
- Previous model versions

### 3. Identify Improvements

If results aren't satisfactory:
- **More training data**: Add more games
- **Better annotations**: Improve description quality
- **Hyperparameter tuning**: Adjust training parameters
- **Prompt engineering**: Refine testing prompts

### 4. Production Integration

Once satisfied:
- Use the **Code** tab to get API integration code
- Implement in your application
- Set up monitoring and logging
- Plan for continuous improvement

---

## Quick Reference

### Testing Workflow ✅

**Step 1: Set System Instructions (Optional but Recommended)**
```
You are a basketball play analyzer. Your job is to analyze video clips 
and return structured JSON data about basketball plays.

For each play, identify:
1. timestamp_seconds: When the play occurs
2. classification: Event type (FG_MAKE, FG_MISS, 3PT_MAKE, etc.)
3. note: Detailed description
4. player_a: Primary player (format: "Player #X (Color Team)")
5. player_b: Secondary player if applicable
6. events: Array of all events

Return response as a JSON array.
```

**Step 2: Write Your Prompt**

For broadcast/wide angle:
```
Analyze this basketball game video from FAR_RIGHT camera angle and identify the play with its events.

This is a FAR_RIGHT camera view that provides wide court view and team formation context.

For the play, provide:
1. timestamp_seconds: The time in the video when the play occurs (number)
2. classification: The primary event type (FG_MAKE, FG_MISS, 3PT_MAKE, 3PT_MISS, FREE_THROW_MAKE, FREE_THROW_MISS, REBOUND, ASSIST, STEAL, BLOCK, TURNOVER, FOUL, TIMEOUT, SUB)
3. note: A detailed description of what happened (string)
4. player_a: The primary player involved (format: "Player #X (Color Team)")
5. player_b: Secondary player if applicable (format: "Player #X (Color Team)")
6. events: Array of all events in the play, each with:
   - label: Event type
   - playerA: Player identifier
   - playerB: Secondary player if applicable

Return a JSON array with the single play. Be precise with timestamps and identify all basketball events.
```

**Step 3: Upload Video or Reference GCS Path**
- Click "+" to upload a clip from your computer
- OR reference GCS: `gs://uball-training-data/games/{game_id}/clips/{play_id}_FAR_RIGHT.mp4`

**Step 4: Submit and Review**
- Click Submit
- Expect JSON output
- Validate the structure and accuracy

### Recommended Settings

```yaml
Model: basketball-pro-cumulative-6games-1761801875
Temperature: 0.4
Top-P: 0.9
Top-K: 40
Max Output Tokens: 2048
```

### Keyboard Shortcuts

- `Enter`: Submit prompt
- `Shift + Enter`: New line in prompt
- `Ctrl/Cmd + K`: Clear conversation
- `Ctrl/Cmd + /`: Show shortcuts

---

## Additional Resources

### Google Cloud Documentation
- [Vertex AI Studio Overview](https://cloud.google.com/vertex-ai/docs/generative-ai/learn/overview)
- [Fine-tuning Gemini Models](https://cloud.google.com/vertex-ai/docs/generative-ai/models/tune-models)
- [Prompt Design Best Practices](https://cloud.google.com/vertex-ai/docs/generative-ai/learn/prompts/prompt-design-strategies)

### Testing Checklist

Before declaring model ready for production:

- [ ] Tested on all play types in training data
- [ ] Verified both broadcast and tactical angles
- [ ] Compared to human analyst quality
- [ ] Tested edge cases and unusual plays
- [ ] Evaluated consistency across multiple runs
- [ ] Documented any failure modes
- [ ] Optimized prompts for best results
- [ ] Generated API integration code
- [ ] Defined success metrics
- [ ] Created deployment plan

---

## Support

For issues or questions:

1. **Model Performance**: Review training data quality and consider additional tuning
2. **Technical Issues**: Check [Vertex AI Status](https://status.cloud.google.com/)
3. **API Integration**: Refer to the Code tab for implementation examples
4. **Architecture Questions**: See [ARCHITECTURE.md](./ARCHITECTURE.md)

---

**Model Version**: basketball-pro-cumulative-6games-1761801875  
**Training Data**: 6 games, 1,587 training examples, 403 validation examples  
**Base Model**: Gemini 2.5 Pro  
**Last Updated**: October 30, 2025

