from flask import Flask, request, jsonify, render_template
import face_recognition
import os
import logging
from pymongo import MongoClient
import numpy as np
from PIL import Image
import io
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow requests from any origin (for development only)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Database connection for voter data
def get_voter_db_connection():
    client = MongoClient('mongodb+srv://sahithyareddy:Sony%402023@smartvoting.kwhts.mongodb.net/?retryWrites=true&w=majority&appName=SmartVoting')
    db = client['voting']  # Original database
    return db
# Database connection for voting data
def get_voting_db_connection():
    client = MongoClient('mongodb+srv://sahithyareddy:Sony%402023@smartvoting.kwhts.mongodb.net/?retryWrites=true&w=majority&appName=SmartVoting')
    db = client['voting_data']  # New database for votes
    return db

@app.route('/verify', methods=['POST'])
def verify_voter():
    try:
        unique_id = request.form.get('unique_id')
        ec_id = request.form.get('ec_id')
        image_file = request.files.get('image')

        logging.debug(f"Received data: unique_id={unique_id}, ec_id={ec_id}, image_file={image_file.filename if image_file else None}")

        # Validate input data
        if not all([unique_id, ec_id, image_file]):
            missing_fields = []
            if not unique_id: missing_fields.append("unique_id")
            if not ec_id: missing_fields.append("ec_id")
            if not image_file: missing_fields.append("image")
            return jsonify({"status": "error", "message": f"Missing required fields: {', '.join(missing_fields)}"})

        # Level 1: Unique ID verification
        db = get_voter_db_connection()
        voter = db.voters.find_one({'unique_id': unique_id})
        logging.debug(f"Database query result: {voter}")

        if not voter:
            return jsonify({"status": "error", "message": "Invalid Unique ID"})

        # Level 2: Election Commission ID verification
        if ec_id != voter['ec_id']:
            return jsonify({"status": "error", "message": "Invalid EC ID"})

        # Check if voter has already voted
        voting_db = get_voting_db_connection()
        existing_vote = voting_db.votes.find_one({'unique_id': unique_id})
        if existing_vote:
            return jsonify({"status": "error", "message": "You have already voted in this election."})

        # Level 3: Face recognition
        try:
            # Read and preprocess the image
            image_bytes = image_file.read()
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            
            # Resize while maintaining aspect ratio
            max_size = 500
            if image.width > max_size or image.height > max_size:
                image.thumbnail((max_size, max_size), Image.LANCZOS)
            
            # Convert to numpy array for face_recognition
            image_np = np.array(image)
            logging.debug(f"Processed image shape: {image_np.shape}")
            
            # Detect faces
            face_locations = face_recognition.face_locations(image_np)
            if not face_locations:
                return jsonify({"status": "error", "message": "No face detected in the image. Please try again with a clearer photo."})
            
            # Get face encodings
            uploaded_encodings = face_recognition.face_encodings(image_np, face_locations)
            if not uploaded_encodings:
                return jsonify({"status": "error", "message": "Could not process facial features. Please try again with a clearer photo."})
            
            # Use the first face detected
            uploaded_encoding = uploaded_encodings[0]
            
        except Exception as e:
            logging.error(f"Error processing image: {e}")
            return jsonify({"status": "error", "message": "Error processing image. Please try again with a different photo."})

        # Get stored encoding from database
        try:
            voter_encoding = np.array(voter['encoding'])
            
            logging.debug(f"Stored encoding length: {len(voter_encoding)}")
            logging.debug(f"Uploaded encoding length: {len(uploaded_encoding)}")

            # Calculate face similarity using face_recognition's built-in compare function
            # This is more reliable than manual normalization and distance calculation
            face_distances = face_recognition.face_distance([voter_encoding], uploaded_encoding)
            
            if len(face_distances) == 0:
                return jsonify({"status": "error", "message": "Face comparison failed. Please try again."})
                
            match_distance = face_distances[0]
            logging.debug(f"Face match distance: {match_distance}")
            
            # Lower distance means better match
            # Typical threshold values: 0.6 for strict matching, 0.7 for more lenient
            threshold = 0.55  # Adjusted for better accuracy
            
            if match_distance > threshold:
                confidence = max(0, min(100, int((1 - match_distance) * 100)))
                logging.debug(f"Face verification failed with confidence: {confidence}%")
                return jsonify({
                    "status": "error", 
                    "message": f"Face verification failed. Confidence level: {confidence}%"
                })
            
            # Calculate confidence percentage (higher is better)
            confidence = max(0, min(100, int((1 - match_distance) * 100)))
            logging.debug(f"Face verified with confidence: {confidence}%")
            
            return jsonify({
                "status": "success", 
                "message": f"Face verified successfully. Confidence level: {confidence}%"
            })
            
        except Exception as e:
            logging.error(f"Error comparing face encodings: {e}")
            return jsonify({"status": "error", "message": "Error during face verification process. Please try again."})
            
    except Exception as e:
        logging.error(f"Error during verification: {e}")
        return jsonify({"status": "error", "message": f"Verification failed: {str(e)}"})

@app.route('/vote', methods=['POST'])
def cast_vote():
    try:
        logging.debug(f"Received vote request: {request.json}")
        unique_id = request.json.get('unique_id')
        ec_id = request.json.get('ec_id')
        party_id = request.json.get('party_id')

        logging.debug(f"Received vote: unique_id={unique_id}, ec_id={ec_id}, party_id={party_id}")

        if not unique_id or not ec_id or not party_id:
            return jsonify({"status": "error", "message": "Missing required fields"})

        # Verify voter exists
        voter_db = get_voter_db_connection()
        voter = voter_db.voters.find_one({'unique_id': unique_id, 'ec_id': ec_id})
        if not voter:
            return jsonify({"status": "error", "message": "Invalid voter credentials"})

        # Get the voting database connection
        voting_db = get_voting_db_connection()

        # Check if voter has already voted
        if voting_db.votes.find_one({'unique_id': unique_id}):
            return jsonify({"status": "error", "message": "Voter has already voted"})

        # Record the vote with timestamp
        vote_data = {
            "unique_id": unique_id,
            "ec_id": ec_id,
            "party_id": party_id,
            "timestamp": datetime.now()
        }
        voting_db.votes.insert_one(vote_data)

        # Update party vote count
        voting_db.party_counts.update_one(
            {"party_id": party_id},
            {"$inc": {"count": 1}},
            upsert=True
        )

        logging.info(f"Vote recorded successfully for unique_id: {unique_id}, party_id: {party_id}")

        return jsonify({"status": "success", "message": "Vote recorded successfully"})

    except Exception as e:
        logging.error(f"Error recording vote: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/get_vote_counts', methods=['GET'])
def get_vote_counts():
    try:
        db = get_voting_db_connection()
        
        # Get all party counts
        party_counts = list(db.party_counts.find({}, {"_id": 0}))
        
        # If no counts are found, count them directly from votes
        if not party_counts:
            # Define the parties
            parties = [
                {'id': 1, 'name': 'Liberal_Centric_Part'},
                {'id': 2, 'name': 'The_Liberal_Party'},
                {'id': 3, 'name': 'National_Liberal_party'}
            ]
            
            party_counts = []
            for party in parties:
                count = db.votes.count_documents({'party_id': party['id']})
                party_counts.append({
                    'party_id': party['id'],
                    'name': party['name'],
                    'count': count
                })
        
        # Get total votes
        total_votes = db.votes.count_documents({})
        
        return jsonify({
            "status": "success",
            "party_counts": party_counts,
            "total_votes": total_votes
        })
    except Exception as e:
        logging.error(f"Error getting vote counts: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/election_commissioner')
def election_commissioner():
    try:
        # Define the parties
        parties = [
            {'id': 1, 'name': 'Liberal Centric Party', 'logo': 'https://th.bing.com/th/id/OIP.dJ_UPeYBh4YoVxV9spS7cgHaE7?rs=1&pid=ImgDetMain'},
            {'id': 2, 'name': 'The Liberal Party', 'logo': 'https://th.bing.com/th/id/OIP.2lWGZPAjW7BcI2SZ0JXdOgHaHa?rs=1&pid=ImgDetMain'},
            {'id': 3, 'name': 'National Liberal Party', 'logo': 'https://th.bing.com/th/id/R.7d7445ebc0b83fa4ca92f5eb87b80dae?rik=OameVzEbUXsRLA&riu=http%3a%2f%2fnationalliberal.org%2fwp-content%2fuploads%2f2023%2f07%2fNLP-SD4-All-Logo.jpg&ehk=M7YStAgFbZL2IrEN9DBYCkbDdKgyh3eSVW%2bmz3SiZu8%3d&risl=&pid=ImgRaw&r=0'}
        ]
        
        # Get vote counts from our API
        db = get_voting_db_connection()
        vote_counts = {}
        total_votes = 0
        
        for party in parties:
            party_id = party['id']
            count = db.votes.count_documents({'party_id': party_id})
            vote_counts[party_id] = count
            total_votes += count
            
        return render_template('election_commissioner.html', 
                              vote_counts=vote_counts, 
                              parties=parties, 
                              total_votes=total_votes)
    except Exception as e:
        logging.error(f"Error rendering election commissioner view: {e}")
        return jsonify({"status": "error", "message": str(e)})

# Simple HTML template for election commissioner dashboard
@app.route('/templates/election_commissioner.html')
def election_commissioner_template():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Election Results Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
    
        <div class="container mt-5">
            <h1 class="text-center mb-4">Election Results Dashboard</h1>
            
            <div class="row">
                <div class="col-md-8 offset-md-2">
                    <div class="card shadow">
                        <div class="card-header bg-primary text-white">
                            <h3 class="card-title mb-0">Vote Counts</h3>
                        </div>
                        <div class="card-body">
                            <table class="table table-striped">
                                <thead>
                                    <tr>
                                        <th>Party</th>
                                        <th>Votes</th>
                                        <th>Percentage</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for party in parties %}
                                    <tr>
                                        <td>
                                            <img src="{{ party.logo }}" alt="{{ party.name }}" width="30" height="30" class="me-2">
                                            {{ party.name }}
                                        </td>
                                        <td>{{ vote_counts[party.id] }}</td>
                                        <td>
                                            {% if total_votes > 0 %}
                                                {{ (vote_counts[party.id] / total_votes) * 100 | round(2) }}%
                                            {% else %}
                                                0%
                                            {% endif %}
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True)