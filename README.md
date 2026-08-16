# Genori Structure Extractor

This project parses natural-language origami requests into a validated `genori.structure.v1` document containing the target object, physical parts, symmetry information, and relative stick lengths. It is powered by the Groq API.

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
python structure/pipeline.py
```
When prompted, type a request like `"an intermediate dragon with two heads"` to receive the structured output.

### 5. Customization
* **System Prompt**: Edit [structure/prompt.txt](structure/prompt.txt) to change how the model decomposes objects.
* **Canonical contract**: Edit [structure/models.py](structure/models.py). Pydantic validates every structure response before it continues through the pipeline.
* **JSON Schema snapshot**: [structure/schema.json](structure/schema.json) is generated from the Pydantic model and is checked for drift by the offline tests.
