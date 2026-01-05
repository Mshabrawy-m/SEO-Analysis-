import streamlit as st
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import requests
from collections import Counter
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import time
import string
import nltk
from nltk.corpus import stopwords
import re
from datetime import datetime
import json
import ssl
try:
    from textstat import flesch_reading_ease
    TEXTSTAT_AVAILABLE = True
except ImportError:
    TEXTSTAT_AVAILABLE = False
    def flesch_reading_ease(text):
        return 0
import concurrent.futures
from io import StringIO

# Download NLTK data
try:
    nltk.download('stopwords', quiet=True)
    nltk.download('punkt', quiet=True)
except:
    pass

# Initialize session state for history
if 'analysis_history' not in st.session_state:
    st.session_state.analysis_history = []
if 'bulk_results' not in st.session_state:
    st.session_state.bulk_results = []

st.set_page_config(
    page_title=" SEO Analysis Tool",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cache for better performance
@st.cache_data(ttl=3600)
def get_metadata(url):
    """Enhanced metadata extraction with comprehensive SEO analysis"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        start_time = time.time()
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Basic metadata
        title_tag = soup.find("title")
        meta_tags = soup.find_all("meta")
        
        # Extract all meta information
        meta_info = {}
        for meta in meta_tags:
            if meta is None:
                continue
            try:
                name = (meta.get('name', '') if hasattr(meta, 'get') else '').lower() or (meta.get('property', '') if hasattr(meta, 'get') else '').lower()
                content = meta.get('content', '') if hasattr(meta, 'get') else ''
                if name and content:
                    meta_info[name] = content
            except (AttributeError, TypeError):
                continue
        
        # Open Graph tags
        og_tags = {}
        for meta in meta_tags:
            if meta is None or not hasattr(meta, 'get'):
                continue
            try:
                property_attr = meta.get('property', '')
                if property_attr.startswith('og:'):
                    og_tags[property_attr] = meta.get('content', '')
            except (AttributeError, TypeError):
                continue
        
        # Headings analysis
        headings = {
            'h1': [h.get_text(strip=True) for h in soup.find_all('h1')],
            'h2': [h.get_text(strip=True) for h in soup.find_all('h2')],
            'h3': [h.get_text(strip=True) for h in soup.find_all('h3')],
        }
        
        # Images analysis
        images = soup.find_all('img')
        images_with_alt = sum(1 for img in images if img and hasattr(img, 'get') and img.get('alt'))
        images_without_alt = len(images) - images_with_alt
        
        # Links analysis
        links = soup.find_all('a', href=True)
        internal_links = []
        external_links = []
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        
        for link in links:
            if link is None or not hasattr(link, 'get'):
                continue
            try:
                href = link.get('href', '')
                if href:
                    absolute_url = urljoin(base_url, href)
                    if urlparse(absolute_url).netloc == urlparse(url).netloc:
                        internal_links.append(absolute_url)
                    else:
                        external_links.append(absolute_url)
            except (AttributeError, TypeError, ValueError):
                continue
        
        # Schema markup detection
        schema_scripts = soup.find_all('script', type='application/ld+json')
        has_schema = len(schema_scripts) > 0
        
        # Canonical URL
        canonical = soup.find('link', rel='canonical')
        canonical_url = None
        if canonical and hasattr(canonical, 'get'):
            try:
                canonical_url = canonical.get('href')
            except (AttributeError, TypeError):
                canonical_url = None
        
        # Robots meta
        robots_meta = meta_info.get('robots', '')
        
        # Get text content
        for script in soup(["script", "style", "nav", "header", "footer"]):
            script.decompose()
        text_content = soup.get_text(separator=' ', strip=True)
        
        # Viewport meta (mobile-friendly check)
        viewport = soup.find('meta', attrs={'name': 'viewport'})
        is_mobile_friendly = viewport is not None
        
        # Twitter Card tags
        twitter_tags = {}
        for meta in meta_tags:
            if meta is None or not hasattr(meta, 'get'):
                continue
            try:
                name = meta.get('name', '')
                if name.startswith('twitter:'):
                    twitter_tags[name] = meta.get('content', '')
            except (AttributeError, TypeError):
                continue
        
        # Language detection
        html_lang = soup.find('html', attrs={'lang': True})
        page_language = None
        if html_lang and hasattr(html_lang, 'get'):
            try:
                page_language = html_lang.get('lang')
            except (AttributeError, TypeError):
                page_language = None
        
        # SSL/HTTPS check
        is_https = urlparse(url).scheme == 'https'
        
        # Image optimization analysis
        image_sizes = []
        large_images = 0
        for img in images:
            if img is None or not hasattr(img, 'get'):
                continue
            try:
                src = img.get('src', '')
                if src:
                    try:
                        img_url = urljoin(base_url, src)
                        img_response = requests.head(img_url, headers=headers, timeout=5, allow_redirects=True)
                        if 'content-length' in img_response.headers:
                            size_kb = int(img_response.headers['content-length']) / 1024
                            image_sizes.append(size_kb)
                            if size_kb > 500:  # Images larger than 500KB
                                large_images += 1
                    except:
                        pass
            except (AttributeError, TypeError):
                continue
        
        # Robots.txt check
        robots_txt_url = urljoin(base_url, '/robots.txt')
        robots_txt_exists = False
        robots_txt_content = None
        try:
            robots_response = requests.get(robots_txt_url, headers=headers, timeout=5)
            if robots_response.status_code == 200:
                robots_txt_exists = True
                robots_txt_content = robots_response.text[:500]  # First 500 chars
        except:
            pass
        
        # Sitemap detection
        sitemap_url = urljoin(base_url, '/sitemap.xml')
        sitemap_exists = False
        try:
            sitemap_response = requests.head(sitemap_url, headers=headers, timeout=5)
            if sitemap_response.status_code == 200:
                sitemap_exists = True
        except:
            pass
        
        # Check for sitemap in robots.txt
        sitemap_in_robots = False
        if robots_txt_content:
            sitemap_in_robots = 'sitemap' in robots_txt_content.lower()
        
        # Broken links check (sample)
        broken_links = 0
        checked_links = 0
        sample_links = list(set(internal_links + external_links))[:10]  # Check first 10 unique links
        for link in sample_links:
            try:
                checked_links += 1
                link_response = requests.head(link, headers=headers, timeout=5, allow_redirects=True)
                if link_response.status_code >= 400:
                    broken_links += 1
            except:
                broken_links += 1
        
        # Readability score
        readability_score = 0
        try:
            if text_content and TEXTSTAT_AVAILABLE:
                readability_score = flesch_reading_ease(text_content[:5000])  # First 5000 chars
        except:
            pass
        
        end_time = time.time()
        analysis_time = end_time - start_time
        
        return {
            "url": url,
            "title": title_tag.text.strip() if title_tag else None,
            "title_length": len(title_tag.text.strip()) if title_tag else 0,
            "meta_description": meta_info.get('description', ''),
            "meta_description_length": len(meta_info.get('description', '')),
            "meta_keywords": meta_info.get('keywords', ''),
            "og_tags": og_tags,
            "twitter_tags": twitter_tags,
            "headings": headings,
            "images_total": len(images),
            "images_with_alt": images_with_alt,
            "images_without_alt": images_without_alt,
            "large_images": large_images,
            "internal_links_count": len(set(internal_links)),
            "external_links_count": len(set(external_links)),
            "broken_links": broken_links,
            "checked_links": checked_links,
            "has_schema": has_schema,
            "schema_count": len(schema_scripts),
            "canonical_url": canonical_url,
            "robots_meta": robots_meta,
            "robots_txt_exists": robots_txt_exists,
            "robots_txt_content": robots_txt_content,
            "sitemap_exists": sitemap_exists,
            "sitemap_in_robots": sitemap_in_robots,
            "is_mobile_friendly": is_mobile_friendly,
            "is_https": is_https,
            "page_language": page_language,
            "readability_score": readability_score,
            "text_content": text_content,
            "response_time": analysis_time,
            "status_code": response.status_code,
            "content_length": len(response.content),
            "timestamp": datetime.now().isoformat()
        }
        
    except requests.exceptions.Timeout:
        st.error("Request timed out. The website took too long to respond.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while fetching the webpage: {str(e)}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        return None

def calculate_seo_score(metadata):
    """Calculate overall SEO score based on various factors"""
    if not metadata or not isinstance(metadata, dict):
        return 0
    
    score = 0
    max_score = 100
    
    # Title (15 points)
    if metadata.get('title'):
        title_len = metadata.get('title_length', 0)
        if 30 <= title_len <= 60:
            score += 15
        elif 20 <= title_len < 30 or 60 < title_len <= 70:
            score += 10
        elif title_len > 0:
            score += 5
    else:
        score += 0
    
    # Meta Description (15 points)
    desc_len = metadata.get('meta_description_length', 0)
    if 120 <= desc_len <= 160:
        score += 15
    elif 100 <= desc_len < 120 or 160 < desc_len <= 180:
        score += 10
    elif desc_len > 0:
        score += 5
    
    # Headings (15 points)
    headings = metadata.get('headings', {})
    h1_count = len(headings.get('h1', []))
    if h1_count == 1:
        score += 15
    elif h1_count > 1:
        score += 5
    if len(headings.get('h2', [])) > 0:
        score += 5
    
    # Images with Alt (10 points)
    images_total = metadata.get('images_total', 0)
    if images_total > 0:
        images_with_alt = metadata.get('images_with_alt', 0)
        alt_ratio = images_with_alt / images_total
        score += int(10 * alt_ratio)
    
    # Mobile Friendly (10 points)
    if metadata.get('is_mobile_friendly', False):
        score += 10
    
    # Schema Markup (10 points)
    if metadata.get('has_schema', False):
        score += 10
    
    # Canonical URL (5 points)
    if metadata.get('canonical_url'):
        score += 5
    
    # Internal Links (5 points)
    internal_links = metadata.get('internal_links_count', 0)
    if internal_links > 0:
        score += min(5, internal_links // 5)
    
    # Content Length (10 points)
    text_content = metadata.get('text_content', '')
    word_count = len(text_content.split()) if text_content else 0
    if word_count >= 300:
        score += 10
    elif word_count >= 200:
        score += 7
    elif word_count >= 100:
        score += 4
    
    return min(score, max_score)

def extract_keywords_tfidf(text_content, top_n=20):
    """Extract keywords using frequency analysis"""
    words = text_content.lower().split()
    stop_words = set(stopwords.words('english'))
    symbols_to_exclude = set(string.punctuation)
    
    filtered_words = [
        word for word in words
        if word.lower() not in stop_words 
        and not any(char in symbols_to_exclude for char in word)
        and len(word) > 2
        and word.isalpha()
    ]
    
    word_counter = Counter(filtered_words)
    return word_counter.most_common(top_n)

def analyze_keywords(text_content):
    """Enhanced keyword analysis"""
    words = text_content.split()
    total_words = len(words)
    word_counter = Counter(words)
    most_common_words = word_counter.most_common()
    return total_words, most_common_words

def generate_recommendations(metadata, seo_score):
    """Generate actionable SEO recommendations"""
    if metadata is None or not isinstance(metadata, dict):
        return [], []
    
    recommendations = []
    priority = []
    
    # Title recommendations
    if not metadata.get('title'):
        recommendations.append({
            "category": "Critical",
            "issue": "Missing Title Tag",
            "recommendation": "Add a descriptive title tag (30-60 characters) that includes your primary keyword.",
            "impact": "High"
        })
        priority.append("Critical")
    else:
        title_length = metadata.get('title_length', 0)
        if title_length < 30:
            recommendations.append({
                "category": "Important",
                "issue": "Title Too Short",
                "recommendation": f"Expand your title tag from {title_length} to 30-60 characters for better SEO.",
                "impact": "Medium"
            })
            priority.append("Important")
        elif title_length > 60:
            recommendations.append({
                "category": "Important",
                "issue": "Title Too Long",
                "recommendation": f"Shorten your title tag from {title_length} to 30-60 characters to avoid truncation.",
                "impact": "Medium"
            })
            priority.append("Important")
    
    # Meta description recommendations
    if not metadata.get('meta_description'):
        recommendations.append({
            "category": "Critical",
            "issue": "Missing Meta Description",
            "recommendation": "Add a compelling meta description (120-160 characters) to improve click-through rates.",
            "impact": "High"
        })
        priority.append("Critical")
    else:
        desc_length = metadata.get('meta_description_length', 0)
        if desc_length < 120:
            recommendations.append({
                "category": "Important",
                "issue": "Meta Description Too Short",
                "recommendation": f"Expand your meta description from {desc_length} to 120-160 characters.",
                "impact": "Medium"
            })
            priority.append("Important")
    
    # H1 recommendations
    headings = metadata.get('headings', {})
    h1_count = len(headings.get('h1', []))
    if h1_count == 0:
        recommendations.append({
            "category": "Critical",
            "issue": "No H1 Tag",
            "recommendation": "Add exactly one H1 tag with your primary keyword to improve SEO structure.",
            "impact": "High"
        })
        priority.append("Critical")
    elif h1_count > 1:
        recommendations.append({
            "category": "Important",
            "issue": "Multiple H1 Tags",
            "recommendation": f"Reduce H1 tags from {h1_count} to 1. Use H2-H6 for subheadings.",
            "impact": "Medium"
        })
        priority.append("Important")
    
    # Image alt text recommendations
    images_total = metadata.get('images_total', 0)
    if images_total > 0:
        images_with_alt = metadata.get('images_with_alt', 0)
        alt_ratio = images_with_alt / images_total
        if alt_ratio < 0.8:
            recommendations.append({
                "category": "Important",
                "issue": "Missing Alt Text on Images",
                "recommendation": f"Add alt text to {metadata.get('images_without_alt', 0)} images for better accessibility and SEO.",
                "impact": "Medium"
            })
            priority.append("Important")
    
    # Mobile friendliness
    if not metadata.get('is_mobile_friendly', False):
        recommendations.append({
            "category": "Critical",
            "issue": "Not Mobile-Friendly",
            "recommendation": "Add a viewport meta tag to make your site mobile-responsive.",
            "impact": "High"
        })
        priority.append("Critical")
    
    # HTTPS
    if not metadata.get('is_https', False):
        recommendations.append({
            "category": "Critical",
            "issue": "Not Using HTTPS",
            "recommendation": "Migrate to HTTPS to improve security and SEO rankings.",
            "impact": "High"
        })
        priority.append("Critical")
    
    # Schema markup
    if not metadata.get('has_schema', False):
        recommendations.append({
            "category": "Recommended",
            "issue": "No Schema Markup",
            "recommendation": "Add structured data (JSON-LD) to help search engines understand your content.",
            "impact": "Low"
        })
        priority.append("Recommended")
    
    # Canonical URL
    if not metadata.get('canonical_url'):
        recommendations.append({
            "category": "Recommended",
            "issue": "No Canonical URL",
            "recommendation": "Add a canonical URL to prevent duplicate content issues.",
            "impact": "Low"
        })
        priority.append("Recommended")
    
    # Content length
    text_content = metadata.get('text_content', '')
    word_count = len(text_content.split()) if text_content else 0
    if word_count < 300:
        recommendations.append({
            "category": "Important",
            "issue": "Low Content Length",
            "recommendation": f"Increase content from {word_count} to at least 300 words for better SEO.",
            "impact": "Medium"
        })
        priority.append("Important")
    
    # Robots.txt
    if not metadata.get('robots_txt_exists', False):
        recommendations.append({
            "category": "Recommended",
            "issue": "No robots.txt File",
            "recommendation": "Create a robots.txt file to guide search engine crawlers.",
            "impact": "Low"
        })
        priority.append("Recommended")
    
    # Sitemap
    if not metadata.get('sitemap_exists', False):
        recommendations.append({
            "category": "Recommended",
            "issue": "No Sitemap.xml",
            "recommendation": "Create a sitemap.xml file to help search engines index your pages.",
            "impact": "Low"
        })
        priority.append("Recommended")
    
    # Broken links
    checked_links = metadata.get('checked_links', 0)
    if checked_links > 0:
        broken_links = metadata.get('broken_links', 0)
        broken_ratio = broken_links / checked_links
        if broken_ratio > 0.1:
            recommendations.append({
                "category": "Important",
                "issue": "Broken Links Detected",
                "recommendation": f"Fix {broken_links} broken links found in sample check.",
                "impact": "Medium"
            })
            priority.append("Important")
    
    # Large images
    large_images = metadata.get('large_images', 0)
    if large_images > 0:
        recommendations.append({
            "category": "Recommended",
            "issue": "Large Images Detected",
            "recommendation": f"Optimize {large_images} large images (>500KB) to improve page speed.",
            "impact": "Low"
        })
        priority.append("Recommended")
    
    # Open Graph tags
    if not metadata.get('og_tags'):
        recommendations.append({
            "category": "Recommended",
            "issue": "No Open Graph Tags",
            "recommendation": "Add Open Graph tags to improve social media sharing appearance.",
            "impact": "Low"
        })
        priority.append("Recommended")
    
    # Readability
    readability_score = metadata.get('readability_score', 0)
    if readability_score > 0 and readability_score < 30:
        recommendations.append({
            "category": "Recommended",
            "issue": "Low Readability Score",
            "recommendation": f"Improve content readability (current: {readability_score:.1f}). Use simpler language and shorter sentences.",
            "impact": "Low"
        })
        priority.append("Recommended")
    
    return recommendations, priority

def analyze_bulk_urls(urls):
    """Analyze multiple URLs in parallel"""
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(get_metadata, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                metadata = future.result()
                if metadata and isinstance(metadata, dict):
                    metadata['seo_score'] = calculate_seo_score(metadata)
                    results.append(metadata)
                else:
                    results.append({
                        "url": url,
                        "error": "Failed to retrieve metadata",
                        "seo_score": 0
                    })
            except Exception as e:
                results.append({
                    "url": url,
                    "error": str(e),
                    "seo_score": 0
                })
    return results

# Main App
st.markdown("""
    <h1 style='text-align:center; margin-bottom:10px;'>
        🔍 Advanced SEO Analysis Tool
    </h1>
    <p style='text-align:center; color:#666;'>
        Comprehensive SEO analysis for any website
    </p>
""", unsafe_allow_html=True)
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    st.markdown("---")
    
    # Analysis mode selection
    analysis_mode = st.radio(
        "Analysis Mode",
        ["Single URL", "Bulk Analysis", "Compare URLs", "History"],
        help="Choose how you want to analyze websites"
    )
    
    st.markdown("---")
    st.info("Enter a website URL to analyze its SEO performance and get actionable insights.")
    
    # History management
    if st.button("🗑️ Clear History"):
        st.session_state.analysis_history = []
        st.session_state.bulk_results = []
        st.success("History cleared!")

# Main content area based on mode
if analysis_mode == "Single URL":
    # URL input
    col1, col2 = st.columns([4, 1])
    with col1:
        url = st.text_input("Enter website URL:", placeholder="https://www.example.com", label_visibility="collapsed")
    with col2:
        analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
    
    url_input = url
    analyze_clicked = analyze_btn

elif analysis_mode == "Bulk Analysis":
    st.subheader("📊 Bulk URL Analysis")
    urls_text = st.text_area(
        "Enter URLs (one per line):",
        placeholder="https://www.example1.com\nhttps://www.example2.com\nhttps://www.example3.com",
        height=150
    )
    analyze_btn = st.button("🔍 Analyze All", type="primary", use_container_width=True)
    
    url_input = None
    analyze_clicked = analyze_btn
    if analyze_btn and urls_text:
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        if urls:
            with st.spinner(f"🔄 Analyzing {len(urls)} URLs... This may take a while."):
                bulk_results = analyze_bulk_urls(urls)
                st.session_state.bulk_results = bulk_results
            
            if bulk_results:
                st.success(f"✅ Analyzed {len(bulk_results)} URLs!")
                
                # Display bulk results
                bulk_data = []
                for result in bulk_results:
                    if result and 'error' not in result:
                        title = result.get('title', 'N/A') or 'N/A'
                        bulk_data.append({
                            "URL": result.get('url', 'N/A'),
                            "SEO Score": result.get('seo_score', 0),
                            "Title": title[:50] if isinstance(title, str) else 'N/A',
                            "Status": result.get('status_code', 'N/A'),
                            "Response Time": f"{result.get('response_time', 0):.2f}s",
                            "Word Count": len(result.get('text_content', '').split()) if result.get('text_content') else 0
                        })
                
                if bulk_data:
                    bulk_df = pd.DataFrame(bulk_data)
                    st.dataframe(bulk_df, use_container_width=True)
                    
                    # Visualization
                    fig = px.bar(bulk_df, x='URL', y='SEO Score', 
                               title='SEO Scores Comparison',
                               color='SEO Score',
                               color_continuous_scale='RdYlGn')
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Download bulk results
                    csv = bulk_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Bulk Results as CSV",
                        data=csv,
                        file_name=f"bulk_seo_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )

elif analysis_mode == "Compare URLs":
    st.subheader("⚖️ URL Comparison")
    col1, col2 = st.columns(2)
    with col1:
        url1 = st.text_input("URL 1:", placeholder="https://www.example1.com", key="url1")
    with col2:
        url2 = st.text_input("URL 2:", placeholder="https://www.example2.com", key="url2")
    
    analyze_btn = st.button("🔍 Compare", type="primary", use_container_width=True)
    
    url_input = None
    analyze_clicked = analyze_btn
    if analyze_btn and url1 and url2:
        with st.spinner("🔄 Analyzing both URLs..."):
            metadata1 = get_metadata(url1)
            metadata2 = get_metadata(url2)
        
        if metadata1 is None or not isinstance(metadata1, dict):
            st.error(f"❌ Failed to analyze URL 1: {url1}")
        elif metadata2 is None or not isinstance(metadata2, dict):
            st.error(f"❌ Failed to analyze URL 2: {url2}")
        else:
            st.success("✅ Comparison Complete!")
            
            # Safe access helper function
            def safe_get(data, key, default=None):
                """Safely get value from dictionary"""
                if data is None or not isinstance(data, dict):
                    return default
                return data.get(key, default)
            
            score1 = calculate_seo_score(metadata1)
            score2 = calculate_seo_score(metadata2)
            
            # Comparison metrics
            headings1 = safe_get(metadata1, 'headings', {})
            headings2 = safe_get(metadata2, 'headings', {})
            text_content1 = safe_get(metadata1, 'text_content', '')
            text_content2 = safe_get(metadata2, 'text_content', '')
            
            comparison_data = {
                "Metric": ["SEO Score", "Title Length", "Meta Description Length", 
                          "H1 Count", "Images with Alt", "Internal Links", 
                          "External Links", "Response Time", "Word Count"],
                url1: [
                    f"{score1}/100",
                    f"{safe_get(metadata1, 'title_length', 0)}",
                    f"{safe_get(metadata1, 'meta_description_length', 0)}",
                    len(safe_get(headings1, 'h1', [])),
                    safe_get(metadata1, 'images_with_alt', 0),
                    safe_get(metadata1, 'internal_links_count', 0),
                    safe_get(metadata1, 'external_links_count', 0),
                    f"{safe_get(metadata1, 'response_time', 0):.2f}s",
                    len(text_content1.split()) if text_content1 else 0
                ],
                url2: [
                    f"{score2}/100",
                    f"{safe_get(metadata2, 'title_length', 0)}",
                    f"{safe_get(metadata2, 'meta_description_length', 0)}",
                    len(safe_get(headings2, 'h1', [])),
                    safe_get(metadata2, 'images_with_alt', 0),
                    safe_get(metadata2, 'internal_links_count', 0),
                    safe_get(metadata2, 'external_links_count', 0),
                    f"{safe_get(metadata2, 'response_time', 0):.2f}s",
                    len(text_content2.split()) if text_content2 else 0
                ]
            }
            
            comp_df = pd.DataFrame(comparison_data)
            st.dataframe(comp_df, use_container_width=True, hide_index=True)
            
            # Visual comparison
            fig = go.Figure()
            title_len1 = safe_get(metadata1, 'title_length', 0)
            title_len2 = safe_get(metadata2, 'title_length', 0)
            desc_len1 = safe_get(metadata1, 'meta_description_length', 0)
            desc_len2 = safe_get(metadata2, 'meta_description_length', 0)
            fig.add_trace(go.Bar(name=url1[:30], x=comp_df['Metric'], y=[score1, title_len1, desc_len1]))
            fig.add_trace(go.Bar(name=url2[:30], x=comp_df['Metric'], y=[score2, title_len2, desc_len2]))
            fig.update_layout(title='SEO Metrics Comparison', barmode='group')
            st.plotly_chart(fig, use_container_width=True)

elif analysis_mode == "History":
    st.subheader("📜 Analysis History")
    if st.session_state.analysis_history:
        history_df = pd.DataFrame(st.session_state.analysis_history)
        st.dataframe(history_df, use_container_width=True)
        
        if st.button("📥 Export History as CSV"):
            csv = history_df.to_csv(index=False)
            st.download_button(
                label="Download",
                data=csv,
                file_name=f"seo_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    else:
        st.info("No analysis history yet. Start analyzing URLs to build your history!")

if analysis_mode == "Single URL" and (url_input or analyze_clicked):
    if not url_input:
        st.warning("Please enter a URL to analyze")
    else:
        try:
            parsed_url = urlparse(url_input)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                st.warning("⚠️ Please enter a valid URL starting with http:// or https://")
            else:
                with st.spinner("🔄 Analyzing website... This may take a few seconds."):
                    metadata = get_metadata(url_input)
                
                if metadata and isinstance(metadata, dict):
                    st.success('✅ Analysis Complete!')
                    
                    # Save to history
                    seo_score = calculate_seo_score(metadata)
                    title = metadata.get('title', 'N/A') or 'N/A'
                    history_entry = {
                        "URL": metadata.get('url', 'N/A'),
                        "SEO Score": seo_score,
                        "Title": title[:50] if isinstance(title, str) else 'N/A',
                        "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    st.session_state.analysis_history.append(history_entry)
                    
                    # SEO Score Card
                    score_color = "🟢" if seo_score >= 70 else "🟡" if seo_score >= 50 else "🔴"
                    
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        st.metric("SEO Score", f"{seo_score}/100", f"{score_color}")
                    with col2:
                        st.metric("Response Time", f"{metadata.get('response_time', 0):.2f}s")
                    with col3:
                        st.metric("Status Code", metadata.get('status_code', 'N/A'))
                    with col4:
                        text_content = metadata.get('text_content', '')
                        word_count = len(text_content.split()) if text_content else 0
                        st.metric("Word Count", f"{word_count:,}")
                    with col5:
                        readability = metadata.get('readability_score', 0)
                        st.metric("Readability", f"{readability:.1f}" if readability > 0 else "N/A")
                    
                    st.markdown("---")
                    
                    # Generate recommendations
                    recommendations, priority = generate_recommendations(metadata, seo_score)
                    
                    # Create tabs for organized display
                    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
                        "📊 Overview", "💡 Recommendations", "📝 Content", "🔗 Links & Images", 
                        "📈 Keywords", "🎯 Technical SEO", "🔒 Security & Performance", "📋 Full Report"
                    ])
                    
                    with tab1:
                        st.header("📊 SEO Overview")
                        
                        # SEO Score Gauge Chart
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            fig = go.Figure(go.Indicator(
                                mode = "gauge+number+delta",
                                value = seo_score,
                                domain = {'x': [0, 1], 'y': [0, 1]},
                                title = {'text': "SEO Score"},
                                delta = {'reference': 50},
                                gauge = {
                                    'axis': {'range': [None, 100]},
                                    'bar': {'color': "darkgreen" if seo_score >= 70 else "orange" if seo_score >= 50 else "darkred"},
                                    'steps': [
                                        {'range': [0, 50], 'color': "lightgray"},
                                        {'range': [50, 70], 'color': "gray"}
                                    ],
                                    'threshold': {
                                        'line': {'color': "red", 'width': 4},
                                        'thickness': 0.75,
                                        'value': 90
                                    }
                                }
                            ))
                            fig.update_layout(height=300)
                            st.plotly_chart(fig, use_container_width=True)
                        
                        with col2:
                            # SEO Factors Breakdown
                            title_score = 15 if metadata.get('title') and 30 <= metadata.get('title_length', 0) <= 60 else (10 if metadata.get('title') else 0)
                            desc_score = 15 if 120 <= metadata.get('meta_description_length', 0) <= 160 else (10 if metadata.get('meta_description_length', 0) > 0 else 0)
                            headings_score = 15 if len(metadata.get('headings', {}).get('h1', [])) == 1 else (5 if len(metadata.get('headings', {}).get('h1', [])) > 0 else 0)
                            images_score = min(10, int(10 * (metadata.get('images_with_alt', 0) / max(metadata.get('images_total', 1), 1))))
                            mobile_score = 10 if metadata.get('is_mobile_friendly', False) else 0
                            schema_score = 10 if metadata.get('has_schema', False) else 0
                            links_score = min(5, metadata.get('internal_links_count', 0) // 5)
                            content_score = 10 if len(metadata.get('text_content', '').split()) >= 300 else (7 if len(metadata.get('text_content', '').split()) >= 200 else (4 if len(metadata.get('text_content', '').split()) >= 100 else 0))
                            
                            factors_data = pd.DataFrame({
                                'Factor': ['Title', 'Meta Desc', 'Headings', 'Images', 'Mobile', 'Schema', 'Links', 'Content'],
                                'Score': [title_score, desc_score, headings_score, images_score, mobile_score, schema_score, links_score, content_score],
                                'Max': [15, 15, 15, 10, 10, 10, 5, 10]
                            })
                            
                            fig = go.Figure()
                            fig.add_trace(go.Bar(
                                name='Current Score',
                                x=factors_data['Factor'],
                                y=factors_data['Score'],
                                marker_color='lightblue'
                            ))
                            fig.add_trace(go.Bar(
                                name='Max Possible',
                                x=factors_data['Factor'],
                                y=factors_data['Max'],
                                marker_color='lightgray',
                                opacity=0.5
                            ))
                            fig.update_layout(
                                title='SEO Factors Breakdown',
                                barmode='overlay',
                                height=300,
                                yaxis_title='Score',
                                xaxis_title='Factor'
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # Headings Structure Visualization
                        st.subheader("Headings Hierarchy")
                        headings = metadata.get('headings', {})
                        h1_count = len(headings.get('h1', []))
                        h2_count = len(headings.get('h2', []))
                        h3_count = len(headings.get('h3', []))
                        
                        if h1_count > 0 or h2_count > 0 or h3_count > 0:
                            headings_df = pd.DataFrame({
                                'Level': ['H1', 'H2', 'H3'],
                                'Count': [h1_count, h2_count, h3_count]
                            })
                            fig = px.bar(headings_df, x='Level', y='Count', 
                                       title='Headings Structure Distribution',
                                       color='Count',
                                       color_continuous_scale='Blues')
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # Title Analysis
                        st.subheader("Title Tag")
                        title = metadata.get('title')
                        if title:
                            title_len = metadata.get('title_length', 0)
                            title_status = "✅ Good" if 30 <= title_len <= 60 else "⚠️ Needs Improvement"
                            st.write(f"**Title:** {title}")
                            st.write(f"**Length:** {title_len} characters {title_status}")
                            if title_len < 30:
                                st.warning("⚠️ Title is too short. Recommended: 30-60 characters")
                            elif title_len > 60:
                                st.warning("⚠️ Title is too long. Recommended: 30-60 characters")
                        else:
                            st.error("❌ No title tag found!")
                        
                        # Meta Description
                        st.subheader("Meta Description")
                        meta_desc = metadata.get('meta_description')
                        if meta_desc:
                            desc_len = metadata.get('meta_description_length', 0)
                            desc_status = "✅ Good" if 120 <= desc_len <= 160 else "⚠️ Needs Improvement"
                            st.write(f"**Description:** {meta_desc}")
                            st.write(f"**Length:** {desc_len} characters {desc_status}")
                            if desc_len < 120:
                                st.warning("⚠️ Description is too short. Recommended: 120-160 characters")
                            elif desc_len > 160:
                                st.warning("⚠️ Description is too long. Recommended: 120-160 characters")
                        else:
                            st.warning("⚠️ No meta description found!")
                        
                        # Headings Structure
                        st.subheader("Headings Structure")
                        headings = metadata.get('headings', {})
                        h1_count = len(headings.get('h1', []))
                        h2_count = len(headings.get('h2', []))
                        h3_count = len(headings.get('h3', []))
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("H1 Tags", h1_count, "✅" if h1_count == 1 else "⚠️")
                        with col2:
                            st.metric("H2 Tags", h2_count)
                        with col3:
                            st.metric("H3 Tags", h3_count)
                        
                        if h1_count == 0:
                            st.error("❌ No H1 tag found!")
                        elif h1_count > 1:
                            st.warning(f"⚠️ Multiple H1 tags found ({h1_count}). Recommended: 1 H1 tag per page.")
                        
                        if headings.get('h1'):
                            st.write("**H1 Tags:**")
                            for h1 in headings.get('h1', []):
                                st.write(f"- {h1}")
                    
                    with tab2:
                        st.header("📝 Content Analysis")
                        
                        text_content = metadata.get('text_content', '')
                        if text_content:
                            total_words, most_common_words = analyze_keywords(text_content)
                        else:
                            total_words = 0
                            most_common_words = []
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Total Words", f"{total_words:,}")
                            st.metric("Characters", f"{len(text_content):,}")
                        with col2:
                            st.metric("Sentences", len(re.split(r'[.!?]+', text_content)) if text_content else 0)
                            st.metric("Paragraphs", len(text_content.split('\n\n')) if text_content else 0)
                        
                        # Content Metrics Visualization
                        st.subheader("Content Metrics")
                        col1, col2 = st.columns(2)
                        with col1:
                            # Word count vs recommended
                            content_metrics = pd.DataFrame({
                                'Metric': ['Current', 'Recommended Min'],
                                'Word Count': [total_words, 300]
                            })
                            fig = px.bar(content_metrics, x='Metric', y='Word Count',
                                       title='Word Count vs Recommended',
                                       color='Metric',
                                       color_discrete_map={'Current': 'lightblue', 'Recommended Min': 'lightgray'})
                            fig.update_layout(height=300)
                            st.plotly_chart(fig, use_container_width=True)
                        
                        with col2:
                            # Readability Score Visualization
                            readability = metadata.get('readability_score', 0)
                            if readability > 0:
                                readability_categories = ['Very Difficult', 'Difficult', 'Fairly Difficult', 
                                                         'Standard', 'Fairly Easy', 'Easy', 'Very Easy']
                                readability_ranges = [0, 30, 50, 60, 70, 80, 90, 100]
                                readability_level = "Not Available"
                                if readability >= 90:
                                    readability_level = "Very Easy"
                                elif readability >= 80:
                                    readability_level = "Easy"
                                elif readability >= 70:
                                    readability_level = "Fairly Easy"
                                elif readability >= 60:
                                    readability_level = "Standard"
                                elif readability >= 50:
                                    readability_level = "Fairly Difficult"
                                elif readability >= 30:
                                    readability_level = "Difficult"
                                else:
                                    readability_level = "Very Difficult"
                                
                                fig = go.Figure(go.Indicator(
                                    mode = "gauge+number",
                                    value = readability,
                                    domain = {'x': [0, 1], 'y': [0, 1]},
                                    title = {'text': f"Readability<br>{readability_level}"},
                                    gauge = {
                                        'axis': {'range': [None, 100]},
                                        'bar': {'color': "green" if readability >= 60 else "orange" if readability >= 30 else "red"},
                                        'steps': [
                                            {'range': [0, 30], 'color': "lightgray"},
                                            {'range': [30, 60], 'color': "gray"}
                                        ]
                                    }
                                ))
                                fig.update_layout(height=300)
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("Readability score not available")
                        
                        # Content Statistics
                        if text_content:
                            sentences = re.split(r'[.!?]+', text_content)
                            sentences = [s.strip() for s in sentences if s.strip()]
                            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
                            avg_word_length = sum(len(word) for word in text_content.split()) / total_words if total_words > 0 else 0
                            
                            stats_data = pd.DataFrame({
                                'Metric': ['Avg Sentence Length', 'Avg Word Length', 'Total Sentences', 'Total Paragraphs'],
                                'Value': [avg_sentence_length, avg_word_length, len(sentences), len(text_content.split('\n\n'))]
                            })
                            
                            fig = px.bar(stats_data, x='Metric', y='Value',
                                       title='Content Statistics',
                                       color='Value',
                                       color_continuous_scale='Viridis')
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # Most Common Words
                        st.subheader("Most Common Words (Top 50)")
                        stop_words = set(stopwords.words('english'))
                        symbols_to_exclude = set(string.punctuation)
                        
                        filtered_words = [
                            (word, count) for word, count in most_common_words
                            if word.lower() not in stop_words 
                            and not any(char in symbols_to_exclude for char in word)
                            and len(word) > 1
                        ]
                        
                        if filtered_words:
                            words, counts = zip(*filtered_words[:50])
                            most_common_df = pd.DataFrame({"Word": words, "Count": counts})
                            st.dataframe(most_common_df, use_container_width=True)
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                fig = px.bar(most_common_df.head(20), x='Word', y='Count', 
                                           title='Top 20 Most Common Words',
                                           color='Count',
                                           color_continuous_scale='Blues')
                                st.plotly_chart(fig, use_container_width=True)
                            with col2:
                                fig = px.pie(most_common_df.head(10), values='Count', names='Word',
                                           title='Top 10 Words Distribution')
                                st.plotly_chart(fig, use_container_width=True)
                    
                    with tab3:
                        st.header("🔗 Links & Images Analysis")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.subheader("Images")
                            images_total = metadata.get('images_total', 0)
                            images_with_alt = metadata.get('images_with_alt', 0)
                            images_without_alt = metadata.get('images_without_alt', 0)
                            st.metric("Total Images", images_total)
                            st.metric("With Alt Text", images_with_alt, 
                                     delta=f"{images_with_alt/images_total*100:.1f}%" if images_total > 0 else "N/A")
                            st.metric("Without Alt Text", images_without_alt)
                            
                            if images_total > 0:
                                alt_ratio = images_with_alt / images_total
                                if alt_ratio < 0.8:
                                    st.warning("⚠️ Some images are missing alt text. This affects accessibility and SEO.")
                                
                                # Alt Text Coverage Visualization
                                alt_data = pd.DataFrame({
                                    'Status': ['With Alt Text', 'Without Alt Text'],
                                    'Count': [images_with_alt, images_without_alt]
                                })
                                fig = px.pie(alt_data, values='Count', names='Status',
                                           title='Image Alt Text Coverage',
                                           color='Status',
                                           color_discrete_map={'With Alt Text': 'green', 'Without Alt Text': 'red'})
                                st.plotly_chart(fig, use_container_width=True)
                        
                        with col2:
                            st.subheader("Links")
                            internal_links = metadata.get('internal_links_count', 0)
                            external_links = metadata.get('external_links_count', 0)
                            st.metric("Internal Links", internal_links)
                            st.metric("External Links", external_links)
                            
                            # Links visualization
                            links_data = pd.DataFrame({
                                'Type': ['Internal', 'External'],
                                'Count': [internal_links, external_links]
                            })
                            fig = px.pie(links_data, values='Count', names='Type', 
                                       title='Link Distribution')
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Links Bar Chart
                            if internal_links > 0 or external_links > 0:
                                fig = px.bar(links_data, x='Type', y='Count',
                                           title='Internal vs External Links',
                                           color='Type',
                                           color_discrete_map={'Internal': 'blue', 'External': 'orange'})
                                st.plotly_chart(fig, use_container_width=True)
                        
                        # Combined Visualization
                        st.subheader("Links & Images Overview")
                        combined_data = pd.DataFrame({
                            'Category': ['Images with Alt', 'Images without Alt', 'Internal Links', 'External Links'],
                            'Count': [images_with_alt, images_without_alt, internal_links, external_links]
                        })
                        fig = px.bar(combined_data, x='Category', y='Count',
                                   title='Links and Images Summary',
                                   color='Count',
                                   color_continuous_scale='Viridis')
                        fig.update_xaxes(tickangle=-45)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with tab4:
                        st.header("📈 Keyword Analysis")
                        
                        # Meta Keywords
                        meta_keywords = metadata.get('meta_keywords', '')
                        if meta_keywords:
                            st.subheader("Meta Keywords")
                            keywords_list = [k.strip() for k in meta_keywords.split(',')]
                            st.write(f"**Total Keywords:** {len(keywords_list)}")
                            st.write(", ".join(keywords_list))
                            
                            # Keyword Density
                            text_content = metadata.get('text_content', '')
                            if keywords_list and text_content:
                                st.subheader("Keyword Density Analysis")
                                total_words = len(text_content.split())
                                keyword_density_data = []
                                
                                for keyword in keywords_list:
                                    keyword_lower = keyword.lower()
                                    text_lower = text_content.lower()
                                    keyword_count = text_lower.count(keyword_lower)
                                    keyword_density = (keyword_count / total_words) * 100 if total_words > 0 else 0
                                    
                                    if keyword_density > 0:
                                        keyword_density_data.append({
                                            "Keyword": keyword,
                                            "Count": keyword_count,
                                            "Density": round(keyword_density, 2)
                                        })
                                
                                if keyword_density_data:
                                    keyword_density_df = pd.DataFrame(keyword_density_data)
                                    st.dataframe(keyword_density_df, use_container_width=True)
                                    
                                    average_density = keyword_density_df["Density"].mean()
                                    st.write(f"**Average Keyword Density:** {average_density:.2f}%")
                                    
                                    # Visualizations
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        fig = px.bar(keyword_density_df, x='Keyword', y='Density',
                                                   title='Keyword Density')
                                        st.plotly_chart(fig, use_container_width=True)
                                    with col2:
                                        fig = go.Figure(data=[go.Pie(
                                            labels=keyword_density_df['Keyword'],
                                            values=keyword_density_df['Density'],
                                            hole=.3
                                        )])
                                        fig.update_layout(title='Keyword Density Distribution')
                                        st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No meta keywords found. Analyzing content for top keywords...")
                            
                            # Extract keywords from content
                            text_content = metadata.get('text_content', '')
                            if text_content:
                                top_keywords = extract_keywords_tfidf(text_content, top_n=20)
                            else:
                                top_keywords = []
                            if top_keywords:
                                st.subheader("Top Keywords from Content")
                                keywords_df = pd.DataFrame(top_keywords, columns=['Keyword', 'Frequency'])
                                st.dataframe(keywords_df, use_container_width=True)
                                
                                fig = px.bar(keywords_df.head(15), x='Keyword', y='Frequency',
                                           title='Top 15 Keywords by Frequency')
                                st.plotly_chart(fig, use_container_width=True)
                    
                    with tab5:
                        st.header("🎯 Technical SEO")
                        
                        # Technical SEO Factors Overview
                        st.subheader("Technical SEO Checklist")
                        tech_factors = pd.DataFrame({
                            'Factor': ['Mobile Friendly', 'Schema Markup', 'Canonical URL', 
                                     'Robots.txt', 'Sitemap', 'HTTPS', 'Language Tag', 'Robots Meta'],
                            'Status': [
                                1 if metadata.get('is_mobile_friendly', False) else 0,
                                1 if metadata.get('has_schema', False) else 0,
                                1 if metadata.get('canonical_url') else 0,
                                1 if metadata.get('robots_txt_exists', False) else 0,
                                1 if metadata.get('sitemap_exists', False) else 0,
                                1 if metadata.get('is_https', False) else 0,
                                1 if metadata.get('page_language') else 0,
                                1 if metadata.get('robots_meta') else 0
                            ]
                        })
                        
                        fig = px.bar(tech_factors, x='Factor', y='Status',
                                   title='Technical SEO Factors Status',
                                   color='Status',
                                   color_continuous_scale=['red', 'green'],
                                   range_y=[0, 1])
                        fig.update_layout(
                            yaxis=dict(tickmode='linear', tick0=0, dtick=1, showticklabels=False),
                            height=400
                        )
                        fig.update_traces(marker_line_color='darkgreen', marker_line_width=2)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Mobile Friendliness
                        st.subheader("Mobile Optimization")
                        is_mobile_friendly = metadata.get('is_mobile_friendly', False)
                        if is_mobile_friendly:
                            st.success("✅ Mobile-friendly (viewport meta tag found)")
                        else:
                            st.error("❌ No viewport meta tag found. Website may not be mobile-friendly.")
                        
                        # Schema Markup
                        st.subheader("Schema Markup")
                        has_schema = metadata.get('has_schema', False)
                        if has_schema:
                            schema_count = metadata.get('schema_count', 0)
                            st.success(f"✅ Schema markup found ({schema_count} schema(s))")
                            
                            # Schema count visualization
                            fig = go.Figure(data=[go.Indicator(
                                mode = "number",
                                value = schema_count,
                                title = {"text": "Schema Markups Found"},
                                number = {"suffix": " schema(s)"}
                            )])
                            fig.update_layout(height=200)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.warning("⚠️ No schema markup found. Consider adding structured data.")
                        
                        # Canonical URL
                        st.subheader("Canonical URL")
                        canonical_url = metadata.get('canonical_url')
                        if canonical_url:
                            st.success(f"✅ Canonical URL: {canonical_url}")
                        else:
                            st.warning("⚠️ No canonical URL found.")
                        
                        # Robots Meta
                        st.subheader("Robots Meta Tag")
                        robots_meta = metadata.get('robots_meta')
                        if robots_meta:
                            st.info(f"Robots directive: {robots_meta}")
                        else:
                            st.info("No robots meta tag (default: index, follow)")
                        
                        # Open Graph Tags
                        og_tags = metadata.get('og_tags')
                        if og_tags:
                            st.subheader("Open Graph Tags")
                            og_df = pd.DataFrame(list(og_tags.items()), 
                                               columns=['Property', 'Content'])
                            st.dataframe(og_df, use_container_width=True)
                            
                            # OG Tags count visualization
                            og_count = len(og_tags)
                            fig = px.pie(values=[og_count, max(0, 10-og_count)], 
                                       names=['Present', 'Missing'],
                                       title=f'Open Graph Tags ({og_count} found)',
                                       color_discrete_map={'Present': 'green', 'Missing': 'lightgray'})
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.warning("⚠️ No Open Graph tags found.")
                    
                    with tab2:
                        st.header("💡 SEO Recommendations")
                        
                        if recommendations:
                            # Group by priority
                            critical = [r for r in recommendations if r['category'] == 'Critical']
                            important = [r for r in recommendations if r['category'] == 'Important']
                            recommended = [r for r in recommendations if r['category'] == 'Recommended']
                            
                            if critical:
                                st.subheader("🔴 Critical Issues")
                                for rec in critical:
                                    with st.expander(f"❌ {rec['issue']} - Impact: {rec['impact']}"):
                                        st.write(rec['recommendation'])
                            
                            if important:
                                st.subheader("🟡 Important Improvements")
                                for rec in important:
                                    with st.expander(f"⚠️ {rec['issue']} - Impact: {rec['impact']}"):
                                        st.write(rec['recommendation'])
                            
                            if recommended:
                                st.subheader("🟢 Recommended Enhancements")
                                for rec in recommended:
                                    with st.expander(f"💡 {rec['issue']} - Impact: {rec['impact']}"):
                                        st.write(rec['recommendation'])
                            
                            # Summary
                            st.markdown("---")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Critical Issues", len(critical))
                            with col2:
                                st.metric("Important", len(important))
                            with col3:
                                st.metric("Recommended", len(recommended))
                            
                            # Recommendations Visualization
                            rec_data = pd.DataFrame({
                                'Priority': ['Critical', 'Important', 'Recommended'],
                                'Count': [len(critical), len(important), len(recommended)]
                            })
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                fig = px.bar(rec_data, x='Priority', y='Count',
                                           title='Recommendations by Priority',
                                           color='Priority',
                                           color_discrete_map={'Critical': 'red', 'Important': 'orange', 'Recommended': 'blue'})
                                st.plotly_chart(fig, use_container_width=True)
                            with col2:
                                fig = px.pie(rec_data, values='Count', names='Priority',
                                           title='Recommendations Distribution',
                                           color='Priority',
                                           color_discrete_map={'Critical': 'red', 'Important': 'orange', 'Recommended': 'blue'})
                                st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.success("🎉 Great job! No major issues found. Your SEO is in good shape!")
                    
                    with tab7:
                        st.header("🔒 Security & Performance")
                        
                        # Security & Performance Overview
                        security_score = sum([
                            1 if metadata.get('is_https', False) else 0,
                            1 if metadata.get('robots_txt_exists', False) else 0,
                            1 if metadata.get('sitemap_exists', False) or metadata.get('sitemap_in_robots', False) else 0,
                        ])
                        
                        response_time = metadata.get('response_time', 0)
                        performance_score = 0
                        if response_time < 1:
                            performance_score = 3
                        elif response_time < 3:
                            performance_score = 2
                        elif response_time < 5:
                            performance_score = 1
                        
                        large_imgs = metadata.get('large_images', 0)
                        broken = metadata.get('broken_links', 0)
                        checked = metadata.get('checked_links', 0)
                        broken_ratio = broken / checked if checked > 0 else 0
                        
                        perf_factors = [
                            1 if response_time < 3 else 0,
                            1 if large_imgs == 0 else 0,
                            1 if broken_ratio < 0.1 else 0,
                        ]
                        performance_score = sum(perf_factors)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            # Security Score
                            security_data = pd.DataFrame({
                                'Factor': ['HTTPS', 'Robots.txt', 'Sitemap'],
                                'Status': [
                                    1 if metadata.get('is_https', False) else 0,
                                    1 if metadata.get('robots_txt_exists', False) else 0,
                                    1 if metadata.get('sitemap_exists', False) or metadata.get('sitemap_in_robots', False) else 0,
                                ]
                            })
                            fig = px.bar(security_data, x='Factor', y='Status',
                                       title='Security Factors',
                                       color='Status',
                                       color_continuous_scale=['red', 'green'],
                                       range_y=[0, 1])
                            fig.update_layout(
                                yaxis=dict(tickmode='linear', tick0=0, dtick=1, showticklabels=False),
                                height=300
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        with col2:
                            # Performance Factors
                            perf_data = pd.DataFrame({
                                'Factor': ['Fast Response', 'No Large Images', 'No Broken Links'],
                                'Status': perf_factors
                            })
                            fig = px.bar(perf_data, x='Factor', y='Status',
                                       title='Performance Factors',
                                       color='Status',
                                       color_continuous_scale=['red', 'green'],
                                       range_y=[0, 1])
                            fig.update_layout(
                                yaxis=dict(tickmode='linear', tick0=0, dtick=1, showticklabels=False),
                                height=300
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("Security")
                            # HTTPS check
                            if metadata.get('is_https'):
                                st.success("✅ HTTPS Enabled - Secure connection")
                            else:
                                st.error("❌ HTTP Only - Not secure. Migrate to HTTPS.")
                            
                            # Robots.txt
                            st.subheader("Robots.txt")
                            if metadata.get('robots_txt_exists'):
                                st.success("✅ robots.txt file found")
                                if metadata.get('robots_txt_content'):
                                    with st.expander("View robots.txt content"):
                                        st.code(metadata.get('robots_txt_content', ''), language='text')
                            else:
                                st.warning("⚠️ robots.txt file not found")
                            
                            # Sitemap
                            st.subheader("Sitemap")
                            if metadata.get('sitemap_exists'):
                                st.success("✅ sitemap.xml found")
                            elif metadata.get('sitemap_in_robots'):
                                st.info("ℹ️ Sitemap referenced in robots.txt")
                            else:
                                st.warning("⚠️ sitemap.xml not found")
                        
                        with col2:
                            st.subheader("Performance")
                            # Response time
                            response_time = metadata.get('response_time', 0)
                            if response_time < 1:
                                st.success(f"✅ Fast response time: {response_time:.2f}s")
                            elif response_time < 3:
                                st.warning(f"⚠️ Moderate response time: {response_time:.2f}s")
                            else:
                                st.error(f"❌ Slow response time: {response_time:.2f}s")
                            
                            # Response time visualization
                            fig = go.Figure(go.Indicator(
                                mode = "gauge+number",
                                value = response_time,
                                domain = {'x': [0, 1], 'y': [0, 1]},
                                title = {'text': "Response Time (seconds)"},
                                gauge = {
                                    'axis': {'range': [None, 5]},
                                    'bar': {'color': "green" if response_time < 1 else "orange" if response_time < 3 else "red"},
                                    'steps': [
                                        {'range': [0, 1], 'color': "lightgreen"},
                                        {'range': [1, 3], 'color': "yellow"}
                                    ],
                                    'threshold': {
                                        'line': {'color': "red", 'width': 4},
                                        'thickness': 0.75,
                                        'value': 3
                                    }
                                }
                            ))
                            fig.update_layout(height=250)
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Large images
                            large_imgs = metadata.get('large_images', 0)
                            if large_imgs > 0:
                                st.warning(f"⚠️ {large_imgs} large images detected (>500KB)")
                            else:
                                st.success("✅ No large images detected")
                            
                            # Broken links
                            broken = metadata.get('broken_links', 0)
                            checked = metadata.get('checked_links', 0)
                            if checked > 0:
                                if broken > 0:
                                    st.warning(f"⚠️ {broken} broken links found (out of {checked} checked)")
                                    # Broken links visualization
                                    broken_data = pd.DataFrame({
                                        'Status': ['Working', 'Broken'],
                                        'Count': [checked - broken, broken]
                                    })
                                    fig = px.pie(broken_data, values='Count', names='Status',
                                               title='Link Status',
                                               color='Status',
                                               color_discrete_map={'Working': 'green', 'Broken': 'red'})
                                    st.plotly_chart(fig, use_container_width=True)
                                else:
                                    st.success(f"✅ No broken links found (checked {checked} links)")
                            
                            # Readability
                            readability = metadata.get('readability_score', 0)
                            if readability > 0:
                                if readability >= 60:
                                    st.success(f"✅ Good readability: {readability:.1f}")
                                elif readability >= 30:
                                    st.warning(f"⚠️ Moderate readability: {readability:.1f}")
                                else:
                                    st.error(f"❌ Low readability: {readability:.1f}")
                            
                            # Page language
                            lang = metadata.get('page_language')
                            if lang:
                                st.info(f"🌐 Page Language: {lang}")
                            else:
                                st.warning("⚠️ No language attribute found")
                    
                    with tab5:
                        st.header("🎯 Technical SEO")
                        
                        # Mobile Friendliness
                        st.subheader("Mobile Optimization")
                        is_mobile_friendly = metadata.get('is_mobile_friendly', False)
                        if is_mobile_friendly:
                            st.success("✅ Mobile-friendly (viewport meta tag found)")
                        else:
                            st.error("❌ No viewport meta tag found. Website may not be mobile-friendly.")
                        
                        # Schema Markup
                        st.subheader("Schema Markup")
                        has_schema = metadata.get('has_schema', False)
                        if has_schema:
                            schema_count = metadata.get('schema_count', 0)
                            st.success(f"✅ Schema markup found ({schema_count} schema(s))")
                        else:
                            st.warning("⚠️ No schema markup found. Consider adding structured data.")
                        
                        # Canonical URL
                        st.subheader("Canonical URL")
                        canonical_url = metadata.get('canonical_url')
                        if canonical_url:
                            st.success(f"✅ Canonical URL: {canonical_url}")
                        else:
                            st.warning("⚠️ No canonical URL found.")
                        
                        # Robots Meta
                        st.subheader("Robots Meta Tag")
                        robots_meta = metadata.get('robots_meta')
                        if robots_meta:
                            st.info(f"Robots directive: {robots_meta}")
                        else:
                            st.info("No robots meta tag (default: index, follow)")
                        
                        # Open Graph Tags
                        og_tags = metadata.get('og_tags')
                        if og_tags:
                            st.subheader("Open Graph Tags")
                            og_df = pd.DataFrame(list(og_tags.items()), 
                                               columns=['Property', 'Content'])
                            st.dataframe(og_df, use_container_width=True)
                        else:
                            st.warning("⚠️ No Open Graph tags found.")
                        
                        # Twitter Card Tags
                        twitter_tags = metadata.get('twitter_tags')
                        if twitter_tags:
                            st.subheader("Twitter Card Tags")
                            twitter_df = pd.DataFrame(list(twitter_tags.items()),
                                                     columns=['Property', 'Content'])
                            st.dataframe(twitter_df, use_container_width=True)
                        else:
                            st.warning("⚠️ No Twitter Card tags found.")
                    
                    with tab8:
                        st.header("📋 Full Report")
                        
                        # Safe access to all metadata fields
                        headings = metadata.get('headings', {})
                        text_content = metadata.get('text_content', '')
                        title = metadata.get('title') or "N/A"
                        meta_desc = metadata.get('meta_description') or "N/A"
                        meta_keywords = metadata.get('meta_keywords') or "N/A"
                        canonical_url = metadata.get('canonical_url') or "N/A"
                        
                        report_data = {
                            "Metric": [
                                "URL", "Title", "Title Length", "Meta Description", 
                                "Meta Description Length", "Meta Keywords",
                                "H1 Count", "H2 Count", "H3 Count",
                                "Total Images", "Images with Alt", "Images without Alt", "Large Images",
                                "Internal Links", "External Links", "Broken Links",
                                "Mobile Friendly", "HTTPS", "Schema Markup", "Canonical URL",
                                "Robots.txt", "Sitemap", "Readability Score", "Page Language",
                                "Response Time", "Status Code", "Content Length",
                                "Word Count", "SEO Score"
                            ],
                            "Value": [
                                metadata.get('url', 'N/A'),
                                title,
                                f"{metadata.get('title_length', 0)} characters",
                                meta_desc,
                                f"{metadata.get('meta_description_length', 0)} characters",
                                meta_keywords,
                                len(headings.get('h1', [])),
                                len(headings.get('h2', [])),
                                len(headings.get('h3', [])),
                                metadata.get('images_total', 0),
                                metadata.get('images_with_alt', 0),
                                metadata.get('images_without_alt', 0),
                                metadata.get('large_images', 0),
                                metadata.get('internal_links_count', 0),
                                metadata.get('external_links_count', 0),
                                f"{metadata.get('broken_links', 0)}/{metadata.get('checked_links', 0)}",
                                "Yes" if metadata.get('is_mobile_friendly', False) else "No",
                                "Yes" if metadata.get('is_https', False) else "No",
                                "Yes" if metadata.get('has_schema', False) else "No",
                                canonical_url,
                                "Yes" if metadata.get('robots_txt_exists', False) else "No",
                                "Yes" if metadata.get('sitemap_exists', False) else "No",
                                f"{metadata.get('readability_score', 0):.1f}" if metadata.get('readability_score', 0) > 0 else "N/A",
                                metadata.get('page_language', 'N/A'),
                                f"{metadata.get('response_time', 0):.2f}s",
                                metadata.get('status_code', 'N/A'),
                                f"{metadata.get('content_length', 0):,} bytes",
                                f"{len(text_content.split()):,}" if text_content else "0",
                                f"{seo_score}/100"
                            ]
                        }
                        
                        report_df = pd.DataFrame(report_data)
                        st.dataframe(report_df, use_container_width=True, hide_index=True)
                        
                        # Export options
                        col1, col2 = st.columns(2)
                        with col1:
                            csv = report_df.to_csv(index=False)
                            st.download_button(
                                label="📥 Download Report as CSV",
                                data=csv,
                                file_name=f"seo_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                        with col2:
                            json_data = json.dumps(metadata, indent=2, default=str)
                            st.download_button(
                                label="📥 Download Report as JSON",
                                data=json_data,
                                file_name=f"seo_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json"
                            )
                    
                    st.markdown("---")
                    response_time = metadata.get('response_time', 0)
                    st.success(f"✅ Analysis completed in {response_time:.2f} seconds")
                    
        except Exception as e:
            st.error(f"❌ Analysis failed: {str(e)}")
            st.exception(e)