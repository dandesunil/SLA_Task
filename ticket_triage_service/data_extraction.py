import httpx
import json
from pathlib import Path

def fetch_and_save_json(url: str, timeout: int = 10, output_file: str = "response.txt"):
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url)
            response.raise_for_status()

            # Check if the server says it's JSON
            content_type = response.headers.get("content-type", "").lower()
            if "application/json" not in content_type:
                print(f"Warning: Response is not JSON (Content-Type: {content_type})")
                print("Saving raw text instead.")
                Path(output_file).parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(response.text)
                return
            # Parse and save JSON
            data = response.json()
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            print(f"✅ JSON saved to '{output_file}'")

    except httpx.RequestError as e:
        print(f"Network error: {e}")
    except httpx.HTTPStatusError as e:
        print(f"HTTP error {e.response.status_code}")
    except json.JSONDecodeError:
        print("Response is not valid JSON.")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    url = "https://docs.netskope.com/wp-json/rest/v1/release-notes"
    fetch_and_save_json(url, output_file="documents/posts.json")
