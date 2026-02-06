"""
Text cleaning utilities for removing images and unwanted content from articles
"""

import re
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


def strip_images_from_html(html_content: str) -> str:
    """
    Remove all <img> tags from HTML content

    Args:
        html_content: HTML string potentially containing <img> tags

    Returns:
        Cleaned HTML string without <img> tags
    """
    if not html_content:
        return html_content

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove all <img> tags
        for img in soup.find_all('img'):
            img.decompose()

        # Return cleaned HTML
        cleaned = str(soup)

        # Log if images were removed
        img_count = html_content.count('<img')
        if img_count > 0:
            logger.debug(f"Removed {img_count} <img> tags from HTML content")

        return cleaned
    except Exception as e:
        logger.error(f"Error stripping images from HTML: {e}")
        # Return original content if parsing fails
        return html_content


def strip_images_from_text(text: str) -> str:
    """
    Remove standalone image URLs from plain text

    Args:
        text: Plain text potentially containing image URLs

    Returns:
        Cleaned text without image URL lines
    """
    if not text:
        return text

    try:
        # Remove lines that are just image URLs
        lines = text.split('\n')
        cleaned_lines = [
            line for line in lines
            if not re.match(r'^https?://.*\.(jpg|jpeg|png|gif|webp|svg)', line.strip(), re.IGNORECASE)
        ]

        cleaned = '\n'.join(cleaned_lines)

        # Log if lines were removed
        removed_count = len(lines) - len(cleaned_lines)
        if removed_count > 0:
            logger.debug(f"Removed {removed_count} image URL lines from text")

        return cleaned
    except Exception as e:
        logger.error(f"Error stripping image URLs from text: {e}")
        # Return original content if processing fails
        return text


def clean_article_content(content: str, is_html: bool = True) -> str:
    """
    Clean article content by removing images

    Args:
        content: Article content (HTML or plain text)
        is_html: Whether content is HTML (True) or plain text (False)

    Returns:
        Cleaned content without images
    """
    if not content:
        return content

    if is_html:
        return strip_images_from_html(content)
    else:
        return strip_images_from_text(content)
