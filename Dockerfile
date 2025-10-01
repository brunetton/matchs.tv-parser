FROM python:3.12-slim

# Copy files to container
COPY pyproject.toml .env matchs_tv.py /app/

# Install PDM (to install project dependencies)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN curl -sSL https://pdm-project.org/install-pdm.py | python3 -
# make PDM available in PATH
ENV PATH="/root/.local/bin:$PATH"

# Install dependencies
WORKDIR /app
# Prevents PDM from creating a virtual environment
RUN pdm config python.use_venv false
RUN pdm config install.cache false
# Install dependencies
RUN pdm install --no-editable

# Define entry point
CMD ["pdm", "run", "python", "matchs_tv.py", "--catch-exceptions"]
