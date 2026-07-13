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
GROQ_API_KEY=your_groq_api_key_here
```

### 4. Usage
Run the extractor script:
```bash
python intent/extractor.py
```
When prompted, type a request like `"an intermediate dragon with two heads"` to receive the structured output.

### 5. Customization
* **Model Selection**: You can open [intent/extractor.py](intent/extractor.py) and change the `model` ID in the chat completion call to any model supported by Groq (e.g., `"qwen-2.5-32b-instruct"` or `"llama3-8b-8192"`).
* **System Prompt**: Edit [intent/prompt.txt](intent/prompt.txt) to change how the model decomposes objects.
* **JSON Schema**: Modify [intent/schema.json](intent/schema.json) to add or adjust output fields.
