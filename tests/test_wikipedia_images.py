import os
import sys

import pytest
import requests

# Add the parent directory to the path so we can import the scripts
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_wikipedia_image_fetch():
    """Test that we can fetch images from Wikipedia API"""
    
    # Test species
    test_species = [
        'Turdus migratorius',   # American Robin
        'Haliaeetus leucocephalus', # Bald Eagle
    ]
    
    for species in test_species:
        # Try scientific name
        sci_name_url = species.replace(' ', '_')
        url = f'https://en.wikipedia.org/api/rest_v1/page/summary/{sci_name_url}'
        
        headers = {'User-Agent': 'Python_BirdNET-Pi/1.0 (Test)'}
        response = requests.get(url=url, headers=headers, timeout=10)
        
        # If we get a successful response, check for an image
        if response.status_code == 200:
            data = response.json()
            assert 'title' in data, f"No title found for {species}"
            
            # Not all species will have images, so we don't assert this
            if 'originalimage' in data and 'source' in data['originalimage']:
                assert data['originalimage']['source'].startswith('https://'), f"Invalid image URL for {species}"


def test_wikipedia_api_structure():
    """Test that the Wikipedia API returns the expected structure"""
    
    # Use a well-known species that should have an image
    species = 'Haliaeetus_leucocephalus'  # Bald Eagle
    url = f'https://en.wikipedia.org/api/rest_v1/page/summary/{species}'
    
    headers = {'User-Agent': 'Python_BirdNET-Pi/1.0 (Test)'}
    response = requests.get(url=url, headers=headers, timeout=10)
    
    assert response.status_code == 200, "Wikipedia API request failed"
    
    data = response.json()
    assert 'title' in data, "No title in response"
    assert 'originalimage' in data, "No image in response"
    assert 'source' in data['originalimage'], "No image source in response"
    
    image_url = data['originalimage']['source']
    assert image_url.startswith('https://'), "Invalid image URL"
    
    # Note: We're not checking if the image URL is directly accessible
    # because Wikipedia may return 403 for direct requests without proper headers
    print(f"Image URL found: {image_url}")
