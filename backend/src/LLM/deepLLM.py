import ollama
import requests
from bs4 import BeautifulSoup
import tiktoken  # pip install tiktoken

class DeepLLM:
    def __init__(self, model_name='deepseek-r1:1.5b'):
        self.model = model_name

    def chat(self, prompt: str) -> str:
        response = ollama.chat(model=self.model, stream=False, messages=[{'role': 'user', 'content': prompt}])
        return response['message']['content']
    
    @staticmethod
    def fetch_article_text(url: str) -> str:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        return "\n".join(p.get_text() for p in paragraphs)

    # @staticmethod
    # def chunk_text_by_token(text: str, max_tokens: int = 500, model_name='gpt2') -> list:
    #     enc = tiktoken.get_encoding(model_name)
    #     words = text.split()
    #     chunks, current_chunk = [], []

    #     current_tokens = 0
    #     for word in words:
    #         token_len = len(enc.encode(word + ' '))
    #         if current_tokens + token_len > max_tokens:
    #             chunks.append(' '.join(current_chunk))
    #             current_chunk = [word]
    #             current_tokens = token_len
    #         else:
    #             current_chunk.append(word)
    #             current_tokens += token_len
    #     if current_chunk:
    #         chunks.append(' '.join(current_chunk))
    #     return chunks

    def summarize_chunk(self, chunk: str) -> str:
        prompt = f"""
        Summarize the following passage into 2-3 concise, factual sentences:\n\n{chunk}
        """
        return self.chat(prompt).strip()

    def getReport(self, url: str, contentList: str) -> str:
        # Step 1: Chunk the content
        # chunks = self.chunk_text_by_token(contentList, max_tokens=500)

        # # Step 2: Summarize each chunk
        # summaries = []
        # for chunk in contentList:
        #     print(f"Processing chunk: {chunk}...")  # Debugging line to check chunk content
        #     print('----------------------')
        #     if len(chunk) < 300:
        #         continue
        #     else:
        #         summary = self.summarize_chunk(chunk)
        #         summaries.append(summary)

        # joined_summary = "\n".join(summaries)

        # Step 3: Final summarization into JSON format
        final_prompt = f"""
        Role:
            - You are a professional journalist assistant.
            - Please rewrite the following news content into a concise summary written in the style of a professional journalist.
            - The tone should be neutral, objective, and informative.

        Rule:
            - Focus on the key facts, and clearly outline the cause and effect of the event.
            - Ensure the summary includes the background (what led to the event), the main event itself, and its impact or potential consequences.
            - Keep the summary between 80 and 100 words.
            - Write in American English.
            - Respond **only** in the exact JSON format below. Do not include any explanation or additional text.
            {{
                "title": "The rewritten news headline here",
                "summary": "The rewritten news summary here. Include the source link at the end."
            }}

        Source:
            - url: {url}

        """

        response = self.chat(final_prompt)
        return response

    

     

if __name__ == "__main__":
    # tttt
    pass

