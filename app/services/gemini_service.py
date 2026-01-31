#!/usr/bin/env python3
"""
Gemini AI Service - Low-level wrapper for Google Gemini API
Handles AI content generation with retry logic and error handling
"""

import os
import logging
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import google.generativeai as genai

logger = logging.getLogger(__name__)


class GeminiService:
    """Service for interacting with Google Gemini AI API"""

    def __init__(self):
        """Initialize Gemini service with API key from environment"""
        self.api_key = os.getenv('GEMINI_API_KEY')

        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found in environment variables")
            raise ValueError("GEMINI_API_KEY environment variable is required")

        # Configure Gemini API
        genai.configure(api_key=self.api_key)

        # Use Gemini 2.0 Flash for cost-effective generation
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

        logger.info("✅ Gemini service initialized successfully")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def generate_content(self, prompt: str, temperature: float = 0.7) -> Optional[str]:
        """
        Generate content using Gemini AI with retry logic

        Args:
            prompt: The prompt to send to Gemini
            temperature: Controls randomness (0.0-1.0). Lower = more focused

        Returns:
            Generated text content or None if failed

        Raises:
            Exception: If generation fails after retries
        """
        try:
            logger.info(f"📝 Generating content with Gemini (temperature={temperature})")

            # Configure generation parameters
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,
            )

            # Generate content
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )

            # Extract text from response
            if response and response.text:
                logger.info(f"✅ Content generated successfully ({len(response.text)} chars)")
                return response.text
            else:
                logger.warning("⚠️ Gemini returned empty response")
                return None

        except Exception as e:
            logger.error(f"❌ Gemini content generation failed: {e}")
            raise

    def generate_structured_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7
    ) -> Optional[str]:
        """
        Generate structured content with optional system instructions

        Args:
            prompt: The main prompt
            system_instruction: Optional system-level instructions
            temperature: Controls randomness

        Returns:
            Generated text content or None if failed
        """
        try:
            # Combine system instruction with prompt if provided
            full_prompt = prompt
            if system_instruction:
                full_prompt = f"{system_instruction}\n\n{prompt}"

            return self.generate_content(full_prompt, temperature=temperature)

        except Exception as e:
            logger.error(f"❌ Structured content generation failed: {e}")
            return None
