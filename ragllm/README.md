To run RagLLM,
1. Make sure Ollama is installed
Go to:
    https://ollama.com/download/linux 
run the command
Pull ollama 3.2
```
    ollama pull llama3.2
```
Then run: 
```
    ollama serve
```
    This should start the port for ollama then run then the program should handle everything by itself
2. Create a virtual environment:
```
python3 -m venv .venv
```
3. Activate it:
```
source .venv/bin/activate
```
4. Install everything from requirements.txt:
```
pip install -r requirements.txt
```