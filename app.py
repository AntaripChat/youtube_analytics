from flask import Flask, render_template, request, jsonify
import requests
import re
import json
from datetime import datetime, timedelta
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

class YouTubeAnalyzer:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"
    
    def extract_channel_id(self, url):
        """Extract channel ID from various YouTube URL formats"""
        patterns = [
            r'youtube\.com/channel/([^/?&]+)',
            r'youtube\.com/c/([^/?&]+)',
            r'youtube\.com/user/([^/?&]+)',
            r'youtube\.com/@([^/?&]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def extract_video_id(self, url):
        """Extract video ID from various YouTube URL formats"""
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:shorts\/)([0-9A-Za-z_-]{11})',
            r'youtu\.be\/([0-9A-Za-z_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def get_channel_id_from_custom_url(self, custom_url):
        """Get channel ID from custom URL using search"""
        search_url = f"{self.base_url}/search"
        params = {
            'part': 'snippet',
            'q': custom_url,
            'type': 'channel',
            'key': self.api_key,
            'maxResults': 1
        }
        
        try:
            response = requests.get(search_url, params=params)
            data = response.json()
            
            if 'items' in data and len(data['items']) > 0:
                return data['items'][0]['snippet']['channelId']
        except Exception as e:
            print(f"Error getting channel ID: {e}")
        
        return None
    
    def get_channel_stats(self, channel_identifier):
        """Get channel statistics with enhanced metrics"""
        if channel_identifier.startswith('UC') and len(channel_identifier) == 24:
            channel_id = channel_identifier
        else:
            channel_id = self.get_channel_id_from_custom_url(channel_identifier)
            if not channel_id:
                return None
        
        # Get channel basic stats
        url = f"{self.base_url}/channels"
        params = {
            'part': 'statistics,snippet,brandingSettings,contentDetails',
            'id': channel_id,
            'key': self.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            if 'items' in data and len(data['items']) > 0:
                channel_data = data['items'][0]
                stats = channel_data['statistics']
                snippet = channel_data['snippet']
                
                # Get recent videos for engagement analysis
                uploads_playlist_id = channel_data['contentDetails']['relatedPlaylists']['uploads']
                recent_videos = self.get_recent_videos(uploads_playlist_id)
                
                # Calculate engagement metrics
                engagement_metrics = self.calculate_channel_engagement(recent_videos, stats)
                
                return {
                    'success': True,
                    'type': 'channel',
                    'title': snippet['title'],
                    'description': snippet.get('description', ''),
                    'custom_url': snippet.get('customUrl', ''),
                    'subscribers': self.format_number(stats.get('subscriberCount', 0)),
                    'views': self.format_number(stats.get('viewCount', 0)),
                    'videos': self.format_number(stats.get('videoCount', 0)),
                    'thumbnail': snippet['thumbnails']['high']['url'],
                    'country': snippet.get('country', 'Not specified'),
                    'published_at': snippet['publishedAt'],
                    'engagement_metrics': engagement_metrics,
                    'recent_videos': recent_videos[:5],  # Last 5 videos
                    'raw_data': {
                        'subscribers': stats.get('subscriberCount', 0),
                        'views': stats.get('viewCount', 0),
                        'videos': stats.get('videoCount', 0)
                    }
                }
        except Exception as e:
            print(f"Error fetching channel stats: {e}")
        
        return {'success': False, 'error': 'Could not fetch channel data'}
    
    def get_recent_videos(self, playlist_id, max_results=10):
        """Get recent videos from uploads playlist"""
        url = f"{self.base_url}/playlistItems"
        params = {
            'part': 'snippet,contentDetails',
            'playlistId': playlist_id,
            'key': self.api_key,
            'maxResults': max_results
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            videos = []
            if 'items' in data:
                for item in data['items']:
                    video_id = item['contentDetails']['videoId']
                    video_stats = self.get_video_stats_by_id(video_id)
                    if video_stats:
                        videos.append(video_stats)
            return videos
        except Exception as e:
            print(f"Error fetching recent videos: {e}")
            return []
    
    def calculate_channel_engagement(self, recent_videos, channel_stats):
        """Calculate channel engagement metrics"""
        if not recent_videos:
            return {}
        
        total_views = sum(int(video['raw_data']['views']) for video in recent_videos)
        total_likes = sum(int(video['raw_data'].get('likes', 0)) for video in recent_videos)
        total_comments = sum(int(video['raw_data'].get('comments', 0)) for video in recent_videos)
        
        subscriber_count = int(channel_stats.get('subscriberCount', 1))
        
        avg_views_per_video = total_views / len(recent_videos)
        engagement_rate = (total_likes + total_comments) / subscriber_count * 100 if subscriber_count > 0 else 0
        
        return {
            'avg_views_per_video': self.format_number(avg_views_per_video),
            'engagement_rate': f"{engagement_rate:.2f}%",
            'total_recent_views': self.format_number(total_views),
            'total_recent_likes': self.format_number(total_likes),
            'total_recent_comments': self.format_number(total_comments)
        }
    
    def get_video_stats(self, video_url):
        """Get video statistics with enhanced metrics"""
        video_id = self.extract_video_id(video_url)
        if not video_id:
            return {'success': False, 'error': 'Invalid video URL'}
        
        # Get video basic stats
        url = f"{self.base_url}/videos"
        params = {
            'part': 'statistics,snippet,contentDetails',
            'id': video_id,
            'key': self.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            if 'items' in data and len(data['items']) > 0:
                video_data = data['items'][0]
                stats = video_data['statistics']
                snippet = video_data['snippet']
                content_details = video_data['contentDetails']
                
                # Get comments
                comments = self.get_video_comments(video_id)
                
                # Calculate engagement metrics
                engagement_metrics = self.calculate_video_engagement(stats)
                
                return {
                    'success': True,
                    'type': 'video',
                    'title': snippet['title'],
                    'description': snippet.get('description', ''),
                    'channel_title': snippet['channelTitle'],
                    'channel_id': snippet['channelId'],
                    'views': self.format_number(stats.get('viewCount', 0)),
                    'likes': self.format_number(stats.get('likeCount', 0)),
                    'comments': self.format_number(stats.get('commentCount', 0)),
                    'duration': content_details['duration'],
                    'published_at': snippet['publishedAt'],
                    'thumbnail': snippet['thumbnails']['high']['url'],
                    'category_id': snippet.get('categoryId', ''),
                    'tags': snippet.get('tags', []),
                    'comments_data': comments,
                    'engagement_metrics': engagement_metrics,
                    'raw_data': {
                        'views': stats.get('viewCount', 0),
                        'likes': stats.get('likeCount', 0),
                        'comments': stats.get('commentCount', 0),
                        'duration': content_details['duration']
                    }
                }
        except Exception as e:
            print(f"Error fetching video stats: {e}")
        
        return {'success': False, 'error': 'Could not fetch video data'}
    
    def get_video_stats_by_id(self, video_id):
        """Get video statistics by video ID"""
        url = f"{self.base_url}/videos"
        params = {
            'part': 'statistics,snippet',
            'id': video_id,
            'key': self.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            if 'items' in data and len(data['items']) > 0:
                video_data = data['items'][0]
                stats = video_data['statistics']
                snippet = video_data['snippet']
                
                return {
                    'title': snippet['title'],
                    'published_at': snippet['publishedAt'],
                    'raw_data': {
                        'views': stats.get('viewCount', 0),
                        'likes': stats.get('likeCount', 0),
                        'comments': stats.get('commentCount', 0)
                    }
                }
        except Exception as e:
            print(f"Error fetching video stats by ID: {e}")
        
        return None
    
    def get_video_comments(self, video_id, max_results=50):
        """Get video comments with sentiment analysis"""
        url = f"{self.base_url}/commentThreads"
        params = {
            'part': 'snippet',
            'videoId': video_id,
            'key': self.api_key,
            'maxResults': max_results,
            'order': 'relevance'
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            comments = []
            if 'items' in data:
                for item in data['items']:
                    comment = item['snippet']['topLevelComment']['snippet']
                    comments.append({
                        'author': comment['authorDisplayName'],
                        'text': comment['textDisplay'],
                        'likes': comment['likeCount'],
                        'published_at': comment['publishedAt'],
                        'sentiment': self.analyze_sentiment(comment['textDisplay'])
                    })
            return comments
        except Exception as e:
            print(f"Error fetching comments: {e}")
            return []
    
    def analyze_sentiment(self, text):
        """Simple sentiment analysis based on keywords"""
        positive_words = ['great', 'awesome', 'amazing', 'love', 'good', 'excellent', 'perfect', 'nice', 'wonderful']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'worst', 'horrible', 'dislike', 'poor']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    def calculate_video_engagement(self, stats):
        """Calculate video engagement metrics"""
        views = int(stats.get('viewCount', 0))
        likes = int(stats.get('likeCount', 0))
        comments = int(stats.get('commentCount', 0))
        
        if views > 0:
            like_ratio = (likes / views) * 100
            comment_ratio = (comments / views) * 100
            total_engagement = like_ratio + comment_ratio
        else:
            like_ratio = comment_ratio = total_engagement = 0
        
        return {
            'like_ratio': f"{like_ratio:.2f}%",
            'comment_ratio': f"{comment_ratio:.2f}%",
            'total_engagement': f"{total_engagement:.2f}%",
            'likes_per_view': f"{(likes/views):.4f}" if views > 0 else "0"
        }
    
    def format_number(self, num):
        """Format numbers to human readable format"""
        try:
            num = int(float(num))
            if num >= 1000000000:
                return f"{num/1000000000:.1f}B"
            elif num >= 1000000:
                return f"{num/1000000:.1f}M"
            elif num >= 1000:
                return f"{num/1000:.1f}K"
            else:
                return str(num)
        except:
            return "0"
    
    def format_duration(self, duration):
        """Format ISO 8601 duration to readable format"""
        # Remove PT prefix
        duration = duration[2:]
        
        # Parse duration components
        hours = 0
        minutes = 0
        seconds = 0
        
        if 'H' in duration:
            hours_part = duration.split('H')[0]
            hours = int(hours_part)
            duration = duration.split('H')[1]
        
        if 'M' in duration:
            minutes_part = duration.split('M')[0]
            minutes = int(minutes_part)
            duration = duration.split('M')[1]
        
        if 'S' in duration:
            seconds_part = duration.split('S')[0]
            seconds = int(seconds_part)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"

# Initialize analyzer
youtube_analyzer = YouTubeAnalyzer(Config.YOUTUBE_API_KEY)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'success': False, 'error': 'Please provide a URL'})
    
    try:
        # Determine if it's a channel or video URL
        if any(pattern in url for pattern in ['youtube.com/channel/', 'youtube.com/c/', 'youtube.com/user/', 'youtube.com/@']):
            # Channel URL
            channel_identifier = youtube_analyzer.extract_channel_id(url)
            if not channel_identifier:
                # Try to get from custom URL
                if 'youtube.com/c/' in url:
                    channel_identifier = url.split('youtube.com/c/')[-1].split('/')[0]
                elif 'youtube.com/@' in url:
                    channel_identifier = url.split('youtube.com/@')[-1].split('/')[0]
                elif 'youtube.com/user/' in url:
                    channel_identifier = url.split('youtube.com/user/')[-1].split('/')[0]
            
            result = youtube_analyzer.get_channel_stats(channel_identifier)
        
        elif any(pattern in url for pattern in ['youtube.com/watch', 'youtu.be/', 'youtube.com/shorts/']):
            # Video URL
            result = youtube_analyzer.get_video_stats(url)
        
        else:
            result = {'success': False, 'error': 'Unsupported URL format'}
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Analysis failed: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)