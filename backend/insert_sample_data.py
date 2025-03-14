from pymongo import MongoClient
import face_recognition
import numpy as np

# Function to insert a single voter
def insert_voter_data(unique_id, ec_id, image_path):
    client = MongoClient('mongodb+srv://sahithyareddy:Sony%402023@smartvoting.kwhts.mongodb.net/?retryWrites=true&w=majority&appName=SmartVoting')
    db = client['voting']

    # Ensure unique_id is a string
    if not isinstance(unique_id, str) or unique_id.strip() == "":
        print(f"Error: Invalid unique_id '{unique_id}'")
        return

    # Check if the voter already exists
    if db.voters.find_one({"unique_id": unique_id}):
        print(f"Error: Voter with unique_id {unique_id} already exists!")
        return

    # Load and encode the image
    try:
        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)

        if not encodings:
            print(f"Error: No face found in {image_path}")
            return

        encoding = encodings[0]

        # Insert voter data
        voter_data = {
            "unique_id": unique_id,
            "ec_id": ec_id,
            "encoding": encoding.tolist()
        }
        db.voters.insert_one(voter_data)
        print(f"Voter {unique_id} inserted successfully!")

    except Exception as e:
        print(f"Error processing {unique_id}: {e}")

# Function to insert multiple voters
def insert_multiple_voters(voters):
    for voter in voters:
        insert_voter_data(voter["unique_id"], voter["ec_id"], voter["image_path"])

if __name__ == "__main__":
    voters = [
        {
            "unique_id": "12345",
            "ec_id": "EC12345",
            "image_path": r"C:\Users\LENOVO\Desktop\sony pro\backend\face_images\12345.jpg"
        },
        {
            "unique_id": "67890",
            "ec_id": "EC67890",
            "image_path": r"C:\Users\LENOVO\Desktop\sony pro\backend\face_images\67890.jpg"
        },
        {
            "unique_id": "13579",
            "ec_id": "EC13579",
            "image_path": r"C:\Users\LENOVO\Desktop\sony pro\backend\face_images\13579.jpg"
        },
        {
           "unique_id": "756972",
            "ec_id": "EC756972",
            "image_path": r"C:\Users\LENOVO\Desktop\sony pro\backend\face_images\756972.jpg"
        }
    ]

    insert_multiple_voters(voters)
