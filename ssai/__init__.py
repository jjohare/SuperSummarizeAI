import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

# Imports for various functionalities
import openai  # Importing OpenAI for GPT-3 interaction
import PyPDF2  # For PDF processing
import pyperclip  # To copy text to clipboard
import requests  # For making HTTP requests
import urllib3  # To handle URL parsing and HTTP requests
from bs4 import BeautifulSoup  # For web scraping
from dotenv import load_dotenv, set_key  # To manage environment variables
from youtube_transcript_api import YouTubeTranscriptApi  # For YouTube transcript extraction

# Load environment variables and disable warnings for unverified HTTPS requests
load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Function to parse command-line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(description='Summarize a URL, PDF, or Youtube Video using ChatGPT.')

    # Define command-line arguments
    parser.add_argument('target', type=str, nargs='?', default=None, help='The URL, PDF, or Youtube Video URL to be summarized.')
    parser.add_argument('--lang', type=str, default='british english', help='Target language for the summary.', dest='lang')
    parser.add_argument('--context', type=str, default=None, help='Add context to the summary', dest='context')
    api_key_help = ('Set the OpenAI API key and store it.\n'
                    'To obtain an OpenAI API key: https://beta.openai.com/signup/')

    parser.add_argument('--OPENAI_KEY', type=str, help=api_key_help)

    args = parser.parse_args()

    # Set OpenAI key if provided
    if args.OPENAI_KEY:
        script_directory = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(script_directory, '.env')
        set_key(env_path, 'OPENAI_KEY', args.OPENAI_KEY)
        print("OPENAI_KEY has been set and stored.")
        exit(0)

    # Check if OpenAI key is set
    if os.getenv("OPENAI_KEY") is None:
        print("OPENAI_KEY is not set. To use SuperSummarizeAI, you need a valid OpenAI API key.")
        print("1. Visit https://beta.openai.com/signup/ to sign up for an OpenAI account.")
        print("2. Once registered, navigate to the API section to obtain your key.")
        print("3. Set your key using: ssai --OPENAI_KEY=YOUR_OPENAI_KEY")
        exit(1)

    # Ensure target is specified
    if args.target is None:
        print("No TARGET specified. Use <TARGET to be summarized>")
        exit(1)

    return args

# Function to run the main process
def run():
    args = parse_arguments()

    target = args.target
    is_url_valid = is_url(target)  # Function to validate URL
    target_language = args.lang
    context = args.context

    print("Extracting data from:", target)
    if not is_url_valid:
        # Extract text from PDF
        text = extract_text_from_pdf(target)  # Function to extract text from PDF
        source = "pdf"
        if text is None:
            print("Failed to extract data from pdf:", target)
            exit(1)
    else:
        # Extract data from URL or YouTube
        if "youtube.com" in target or "youtu.be" in target:
            text = extract_transcript(target)  # Function to extract YouTube transcript
            source = "youtube"
        else:
            text = extract_text_from_url(target)  # Function to extract text from URL
            source = "website"

        if text is None:
            print("Failed to extract data from:", target)
            exit(1)

    print("Data extracted ("+source+")")
    if context is not None:
        print("Context:", context)
    print(f"Creating ChatGPT summary in {target_language}. This may take a while...")
    
    try:
        # Get summary from ChatGPT
        chatgpt_result = chatgpt(text, source, target_language, context)  # Function to interact with ChatGPT
        chatgpt_result = chatgpt_result.strip()
        chatgpt_json = json.loads(chatgpt_result)
    except Exception as e:
        print("Error parsing ChatGPT response: ", e)
        exit(1)
    
    title = chatgpt_json.get('title', 'Title Not Found')
    copy_to_clipboard(format_text(target, chatgpt_json))  # Function to format and copy text to clipboard

# Function to get summary from ChatGPT
def chatgpt(text, source, target_language="british english", context=None):
    additional_context = ""
    if context is not None:
        additional_context = "Additional context: " + context

    system_text = f"""
    The data below was extracted from a {source}. Generate an insightful summary of this data in {target_language}. {additional_context}. Use \\n to break line, if needed. Return the result as a JSON in the following format:
    {{
        title: "Title of your summary",
        summary: "Summary of the article"
    }}
    """
    text_to_chatgpt = system_text + text
    # Add the rest of your chatgpt function code here, including making requests to OpenAI and handling responses

import re
from urllib.request import urlopen
from PyPDF2 import PdfFileReader
from io import BytesIO

def is_url(string):
    """
    Check if the given string is a valid URL.

    Args:
    string (str): The string to be checked.

    Returns:
    bool: True if the string is a valid URL, False otherwise.
    """
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, string) is not None

def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF file.

    Args:
    pdf_path (str): The file path to the PDF from which to extract text.

    Returns:
    str: Extracted text from the PDF.
    """
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PdfFileReader(file)
            text = ''
            for page_num in range(pdf_reader.getNumPages()):
                text += pdf_reader.getPage(page_num).extractText()
            return text
    except Exception as e:
        print(f"Error reading PDF file at {pdf_path}: {e}")
        return None

def extract_text_from_url(url):
    """
    Extract text from the contents of a URL.

    Args:
    url (str): The URL from which to extract text.

    Returns:
    str: Extracted text from the URL's content.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
        soup = BeautifulSoup(response.text, 'html.parser')
        return ' '.join([p.text for p in soup.find_all('p')])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return None

if __name__ == "__main__":
    run()
