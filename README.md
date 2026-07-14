# Origami Intent Extractor

This project parses natural language origami requests into a structured JSON format specifying the target object, difficulty level, and physical parts with symmetry information. It is powered by the Groq API using Qwen models.

## Setup Instructions

### 1. Prerequisites
* **Python**: Python 3.11 or 3.12 is recommended.

### 2. Installation
Install the project dependencies from the root directory:
```bash
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory:
```env
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### 4. Usage
Run the extractor script:
```bash
python intent/extractor.py
```
When prompted, type a request like `"an intermediate dragon with two heads"` to receive the structured output.

### 5. Customization
* **System Prompt**: Edit [intent/prompt.txt](intent/prompt.txt) to change how the model decomposes objects.
* **JSON Schema**: Modify [intent/schema.json](intent/schema.json) to add or adjust output fields.
