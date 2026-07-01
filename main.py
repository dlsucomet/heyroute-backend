import os
import io
import wave
import httpx
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import get_db
from vad_utils import apply_vad_filter
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="HeyRoute API")

# ASR_URL = "http://altdsidccf.dlsu.edu.ph:33070/transcribe"
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
	
@app.post("/api/voice/vad")
async def process_voice_activity(
	audio_file: UploadFile = File(...), 
	download: bool = Query(False, description="Set to true to download the cleaned audio file")
	):
	try:
		audio_bytes = await audio_file.read()

		clean_audio_bytes = apply_vad_filter(audio_bytes)

		wav_io = io.BytesIO()
		with wave.open(wav_io, 'wb') as wav_file:
			wav_file.setnchannels(1)  # Mono
			wav_file.setsampwidth(2)  # 16-bit samples
			wav_file.setframerate(16000)  # 16 kHz sample rate
			wav_file.writeframes(clean_audio_bytes)

		wav_io.seek(0)

		if download:
			return Response(
				content = wav_io.getvalue(),
				media_type = "audio/wav",
				headers = {"Content-Disposition": f"attachment; filename=clean_{audio_file.filename}.wav"}
			)
		
		async with httpx.AsyncClient(timeout=30.0) as client:
			files = {'file': (f"clean_{audio_file.filename}.wav", wav_io, "audio/wav")}
			headers = {'X-API-Key': ASR_API_KEY}

			asr_response = await client.post(ASR_URL, files=files, headers=headers)

			if asr_response.status_code != 200:
				raise HTTPException(status_code = asr_response.status_code,
									detail = f"ASR Server Error: {asr_response.text}"
				)
			
			transcription_data = asr_response.json()
		
		# return to the user
		return {
			"filename": audio_file.filename,
			"original_bytes": len(audio_bytes),
			"clean_bytes": len(clean_audio_bytes),
			"transcription": transcription_data,
			"message": "Audio processed and transcribed successfully."
		}
	
	except httpx.RequestError as exc:
		raise HTTPException(status_code=500, detail=f"Failed to connect to ASR server: {str(exc)}")
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error processing audio file: {str(e)}")