from langchain_openai import ChatOpenAI, OpenAIEmbeddings
import httpx

client = httpx.Client(verify=False)

import os

llm = ChatOpenAI(
    base_url="https://genailab.tcs.in",
    model="gemini-3.1-pro-preview",
    api_key='sk-2tSHoSmhC1k864E_ZQAOLg', # Replace with your actual API key
    http_client=client
)

print("LLM instance created successfully")

# embedding_model = OpenAIEmbeddings(
#     base_url="https://genailab.tcs.in",
#     model="azure/genailab-maas-text-embedding-3-large",
#     api_key='sk-2tSHoSmhC1k864E_ZQAOLg', # Replace with your actual API key
#     http_client=client
# )

print("Embedding Model instance created successfully")

print(llm.invoke("What is the current status of the France student Protest").content)

# DON'T EDIT THIS FILE


# [SSLError] [SSL: CERTIFICATE_VERIFY_FAILED]
# https://stackoverflow.com/questions/76106366/how-to-use-tiktoken-in-offline-mode-computer


# TO INSTALL AIDER (OPEN SOURCE EQUILEVANT OF WINDSURF OR CURSOR)
# RUN THE FOLLOWING COMMANDS

# python -m pip install aider-install
# Add the installed path to your user environment variable
# Navigate to https://aider.chat/
# download the Root certificate
# Ex: setx SSL_CERT_FILE=<full path of the location of the certifcate with file name>
# now run the following command
# aider-install

# Add the aider installed path to your user environment variable
# Ex: setx   OPENAI_API_KEY=sk-Key
# Ex: setx OPENAI_API_BASE genailab.tcs.in