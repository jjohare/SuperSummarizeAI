import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import openai  # Updated import for OpenAI
import PyPDF2
import pyperclip
import requests
import urllib3
from bs4 import BeautifulSoup
from dotenv import load_dotenv, set_key
from youtube_transcript_api import YouTubeTranscriptApi

# Load environment variables and disable warnings for unverified HTTPS requests
load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Function to parse command-line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(description='Summarize a URL, PDF, or Youtube Video using ChatGPT.')

    parser.add_argument('target', type=str, nargs='?', default=None, help='The URL, PDF, or Youtube Video URL to be summarized.')
    parser.add_argument('--lang', type=str, default='british english', help='Target language for the summary.', dest='lang')
    parser.add_argument('--context', type=str, default=None, help='Add context to the summary', dest='context')
    api_key_help = ('Set the OpenAI API key and store it.\n'
                    'To obtain an OpenAI API key: https://beta.openai.com/signup/')

    parser.add_argument('--OPENAI_KEY', type=str, help=api_key_help)

    args = parser.parse_args()

    if args.OPENAI_KEY:
        script_directory = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(script_directory, '.env')
        set_key(env_path, 'OPENAI_KEY', args.OPENAI_KEY)
        print("OPENAI_KEY has been set and stored.")
        exit(0)

    if os.getenv("OPENAI_KEY") is None:
        print("OPENAI_KEY is not set. To use SuperSummarizeAI, you need a valid OpenAI API key.")
        print("1. Visit https://beta.openai.com/signup/ to sign up for an OpenAI account.")
        print("2. Once registered, navigate to the API section to obtain your key.")
        print("3. Set your key using: ssai --OPENAI_KEY=YOUR_OPENAI_KEY")
        exit(1)

    if args.target is None:
        print("No TARGET specified. Use <TARGET to be summarized>")
        exit(1)

    return args

# Function to run the main process
def run():
    args = parse_arguments()

    target = args.target
    is_url_valid = is_url(target)
    target_language = args.lang
    context = args.context

    print("Extracting data from:", target)
    if not is_url_valid:
        text = extract_text_from_pdf(target)
        source = "pdf"
        if text is None:
            print("Failed to extract data from pdf:", target)
            exit(1)
    else:
        if "youtube.com" in target or "youtu.be" in target:
            text = extract_transcript(target)
            source = "youtube"
        else:
            text = extract_text_from_url(target)
            source = "website"

        if text is None:
            print("Failed to extract data from:", target)
            exit(1)

    print("Data extracted ("+source+")")
    if context is not None:
        print("Context:", context)
    print(f"Creating ChatGPT summary in {target_language}. This may take a while...")
    chatgpt_result = chatgpt(text, source, target_language, context)
    print("ChatGPT summary done")
    try:
        chatgpt_result = chatgpt_result.strip()
        chatgpt_json = json.loads(chatgpt_result)
    except Exception as e:
        print("Error parsing ChatGPT response: ", e)
        exit(1)
    title = chatgpt_json.get('title', 'Title Not Found')
    copy_to_clipboard(format_text(target, chatgpt_json))

# Function to get summary from ChatGPT
def chatgpt(text, source, target_language="british english", context=None):
    try:
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
