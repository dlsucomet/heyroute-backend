import os
import io
import wave
import httpx
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Query, Header
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import get_db
from vad_utils import apply_vad_filter
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="HeyRoute API")

# --- ASR server handoff configuration ---
ASR_URL = "http://172.16.3.217:80/transcribe"
ASR_API_KEY = os.getenv("ASR_API_KEY")
if not ASR_API_KEY:
	raise ValueError("CRITICAL ERROR: ASR_API_KEY is missing from the environment variables.")


@app.get("/health")
async def health_check():
	return {"status": "online", "message": "The HeyRoute FastAPI server is running!"}

@app.get("/db-check")
async def db_check(db: AsyncSession = Depends(get_db)):
	try:
		await db.execute(text("SELECT 1"))
		return {"database_status": "connected", "message": "Successfully communicating with postgresql"}
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

# --- Voice processing endpoint ---
# This endpoint handles the flow of audio file processing, namely:
# 1. App sends audio file to this endpoint (DONE)
# 2. This endpoint applies VAD to clean the audio (DONE)
# 3. This endpoint sends the cleaned audio to the ASR server for transcription (DONE)
# 4. This endpoint receives the transcription from the ASR server (DONE)
# 5. This endpoint sends the transcription to the LLM server for intent extraction (TODO)
# 6. This endpoint receives the intent from the LLM server (TODO)
# 7. This endpoint sends the intent back to the App (TODO)

@app.post("/api/voice/vad")
async def process_voice_activity(
	audio_file: UploadFile = File(...), 
	download: bool = Query(False, description="Set to true to download the cleaned audio file"),
	x_user_id: str = Header(..., description="User ID for database querying"),
	x_session_id: str = Header(..., description="Session ID for the current routing trip")
	):

	print(f"Processing audio file: {audio_file.filename} for user: {x_user_id}, session: {x_session_id}")
	
	try:
		# Read the uploaded audio file
		audio_bytes = await audio_file.read()

		# Run the raw audio through the VAD filter utility
		clean_audio_bytes = apply_vad_filter(audio_bytes)

		# Convert the cleaned audio bytes to a WAV format for ASR processing
		wav_io = io.BytesIO()
		with wave.open(wav_io, 'wb') as wav_file:
			wav_file.setnchannels(1)  # Mono
			wav_file.setsampwidth(2)  # 16-bit samples
			wav_file.setframerate(16000)  # 16 kHz sample rate
			wav_file.writeframes(clean_audio_bytes)

		# Reset the BytesIO stream position to the beginning for reading
		wav_io.seek(0)

		# If the user requested to download the cleaned audio, return it as a response (this skips the ASR step)
		if download:
			return Response(
				content = wav_io.getvalue(),
				media_type = "audio/wav",
				headers = {"Content-Disposition": f"attachment; filename=clean_{audio_file.filename}.wav"}
			)
		
		# Send the cleaned audio to the ASR server for transcription
		async with httpx.AsyncClient(timeout=30.0) as client:
			files = {'file': (f"clean_{audio_file.filename}.wav", wav_io, "audio/wav")}
			headers = {'X-API-Key': ASR_API_KEY}

			asr_response = await client.post(ASR_URL, files=files, headers=headers)

			# Check if the ASR server responded with an error
			if asr_response.status_code != 200:
				raise HTTPException(status_code = asr_response.status_code,
									detail = f"ASR Server Error: {asr_response.text}"
				)
			
			# Extract the transcription data from the ASR server's response
			transcription_data = asr_response.json()
		
		# Return the transcription data along with some metadata about the processed audio
		return {
			"filename": audio_file.filename,
			"original_bytes": len(audio_bytes),
			"clean_bytes": len(clean_audio_bytes),
			"transcription": transcription_data,
			"message": "Audio processed and transcribed successfully."
		}
	
	except httpx.RequestError as exc:
		raise HTTPException(status_code=500, detail=f"Unable to connect to the ASR server: {str(exc)}")
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Unable to process the audio file: {str(e)}")