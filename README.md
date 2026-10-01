## Python version to use
- Use version 3.14 and up

## Install dependencies
```bash
py -m pip install fastapi "uvicorn[standard]"
```
## Running the Application

- Start the development server:

```bash
py -m uvicorn main:app --reload
```

- The API will be available at:

```http://127.0.0.1:8000/docs```
