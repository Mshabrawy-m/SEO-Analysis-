# [Website SEO Analysis Tool](https://your-app-url.streamlit.app/)

Website SEO Analysis Tool is a Streamlit-based web application designed for analyzing the SEO aspects of any website. It provides comprehensive insights into metadata, keywords, keyword density, and most common words present in the webpage content.

*Note: Keywords are currently extracted from the meta keyword tag. In its current state, the app considers words present in the meta keyword tag as keywords. Future updates will include more sophisticated algorithms to determine keywords, making it a beginner-friendly project. Contributions and improvements are welcome!*

## Features

- **Metadata Analysis:** Retrieve and display the title, keywords, and description of any web page.

- **Keywords Analysis:** Analyze and display the keywords used in the web page.

- **Keyword Density Analysis:** Visualize the distribution of keyword density through pie charts, histograms, and bar charts.

- **Most Common Words Analysis:** Identify and display the most common words used in the article content.

## Getting Started

### Prerequisites

Make sure you have Python installed. You can download it from [python.org](https://www.python.org/downloads/).

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/Srish0218/GeeksforGeeks-SEO-Analysis-Web-App.git
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Usage
1. Run the Streamlit app:
   ```bash
   streamlit run app.py
   ```

2. Open the app in your web browser.

3. Enter any website URL you want to analyze and explore the SEO insights.

### Example URLs to Try
- News websites (e.g., bbc.com, reuters.com)
- Tech blogs (e.g., techcrunch.com)
- Educational sites (e.g., wikipedia.org)
- Company websites

### Contributing
If you would like to contribute to the project, feel free to fork the repository and submit pull requests.

### License
This project is licensed under the MIT License.

### Acknowledgments
1. [Streamlit](https://streamlit.io/)
2. [Beautiful Soup](https://pypi.org/project/beautifulsoup4/)
3. [NLTK](https://www.nltk.org/)