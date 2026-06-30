import io
import wave
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import get_db
from vad_utils import apply_vad_filter

app = FastAPI(title="HeyRoute API")

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

		if download:
			wav_io = io.BytesIO()
			with wave.open(wav_io, 'wb') as wav_file:
				wav_file.setnchannels(1)  # Mono
				wav_file.setsampwidth(2)  # 16-bit samples
				wav_file.setframerate(16000)  # 16 kHz sample rate
				wav_file.writeframes(clean_audio_bytes)
			
			return Response(
				content = wav_io.getvalue(),
				media_type = "audio/wav",
				headers = {"Content-Disposition": f"attachment; filename=clean_{audio_file.filename}.wav"}
			)
		
		return {
			"filename": audio_file.filename,
			"original_bytes": len(audio_bytes),
			"clean_bytes": len(clean_audio_bytes),
			"message": "Audio processed through VAD filter successfully."
		}
	
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error processing audio file: {str(e)}")