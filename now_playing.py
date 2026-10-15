"""Windows media sessions: select actively playing browser/player session."""
import asyncio
import threading
import time
from datetime import datetime, timezone

EMPTY={'music_title':'','music_artist':'','music_playing':False,'music_art':None,'music_position':None,'music_duration':None}

class NowPlaying(threading.Thread):
    def __init__(self,stop,events):
        super().__init__(daemon=True)
        self.stop,self.events=stop,events
        self.lock=threading.Lock()
        self.data=dict(EMPTY)
        self._last_message=None
        self._sample_time=time.monotonic()
        self._last_good_timeline=None
        self._last_good_track=None
        self._track_id=None
        self._anchor_position=0.0
        self._anchor_time=time.monotonic()

    def get(self):
        with self.lock:
            result=dict(self.data)
            age=max(0.0,time.monotonic()-self._anchor_time)
            anchor=self._anchor_position
        if result.get('music_playing') and result.get('music_position') is not None:
            result['music_position']=min(result['music_duration'] or float('inf'),anchor+age)
        return result

    def _report(self,message):
        if message!=self._last_message:
            self._last_message=message
            self.events.put(('Music',message))

    def run(self):
        try:
            asyncio.run(self._poll())
        except Exception as exc:
            self._report('Media service error: '+repr(exc))

    async def _read_art(self,thumbnail):
        if thumbnail is None:
            return None
        from winrt.windows.storage.streams import DataReader
        stream=await thumbnail.open_read_async()
        size=min(int(stream.size),2_000_000)
        if size<=0:return None
        reader=DataReader(stream)
        await reader.load_async(size)
        # Python WinRT read_bytes expects a writable byte buffer, not a length.
        # Passing an integer raises TypeError("a bytes-like object is required, not 'int'").
        buffer=bytearray(size)
        result=reader.read_bytes(buffer)
        if isinstance(result,(bytes,bytearray,memoryview)):
            return bytes(result)
        return bytes(buffer)

    async def _poll(self):
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
        manager=await GlobalSystemMediaTransportControlsSessionManager.request_async()
        self._report('Windows media monitor started')
        while not self.stop.is_set():
            chosen=dict(EMPTY)
            try:
                sessions=list(manager.get_sessions())
                current=manager.get_current_session()
                if current is not None:
                    sessions.sort(key=lambda s:s.source_app_user_model_id!=current.source_app_user_model_id)
                for session in sessions:
                    try:
                        media=await session.try_get_media_properties_async()
                        title=str(media.title or '').strip()
                        if not title:continue
                        status=session.get_playback_info().playback_status
                        # WinRT enum can be an int or string depending on package version.
                        playing=(getattr(status,'value',status)==4 or str(status).lower().endswith('playing'))
                        candidate={'music_title':title,'music_artist':str(media.artist or ''),
                                   'music_playing':bool(playing),'music_art':None,'music_position':None,'music_duration':None}
                        try:
                            timeline=session.get_timeline_properties()
                            duration=max(0.0,(timeline.end_time-timeline.start_time).total_seconds())
                            position=max(0.0,(timeline.position-timeline.start_time).total_seconds())
                            # WinRT positions are snapshots: extrapolate using the
                            # Windows timestamp at which the snapshot was recorded.
                            # Without this, a browser may repeatedly report 0:00.
                            last=timeline.last_updated_time
                            if playing and isinstance(last,datetime):
                                if last.tzinfo is None:
                                    last=last.replace(tzinfo=timezone.utc)
                                age=(datetime.now(timezone.utc)-last.astimezone(timezone.utc)).total_seconds()
                                if 0<=age<86400:
                                    position+=age
                            # The timeline's last_updated_time is a Windows DateTime.
                            # The time since the last update may be used to extrapolate,
                            # but we anchor our own monotonic clock to avoid drift.
                            if duration>0:
                                candidate['music_duration']=duration
                                candidate['music_position']=min(duration,position)
                        except Exception:
                            pass
                        if playing or not chosen['music_title']:
                            chosen=candidate
                            selected=session
                        if playing:break
                    except Exception as exc:
                        self._report('Session read error: '+repr(exc))
                if chosen['music_title']:
                    try:
                        chosen['music_art']=await self._read_art((await selected.try_get_media_properties_async()).thumbnail)
                    except Exception as exc:
                        self._report('Album art unavailable: '+repr(exc))
                elif not sessions:
                    self._report('No Windows media sessions found. Check browser media controls.')
                else:
                    self._report('Media sessions found but no track title provided.')
            except Exception as exc:
                self._report('Media polling error: '+repr(exc))
            with self.lock:
                now=time.monotonic()
                track=(chosen.get('music_title'),chosen.get('music_artist'))
                # Some Windows media sessions intermittently omit the timeline.
                # Preserve the last valid duration/position for the same track.
                if track != self._last_good_track:
                    self._last_good_track=track
                    self._last_good_timeline=None
                if chosen.get('music_duration') and chosen.get('music_position') is not None:
                    self._last_good_timeline=(chosen['music_duration'],chosen['music_position'])
                elif self._last_good_timeline and track[0]:
                    chosen['music_duration']=self._last_good_timeline[0]
                    chosen['music_position']=self._anchor_position + (now-self._anchor_time if chosen.get('music_playing') else 0)
                position=chosen.get('music_position')
                duration=chosen.get('music_duration')
                if track!=self._track_id:
                    self._track_id=track
                    self._anchor_position=max(0.0,position or 0.0)
                    self._anchor_time=now
                elif position is not None and duration:
                    predicted=self._anchor_position+(now-self._anchor_time if chosen.get('music_playing') else 0)
                    # Some browsers keep reporting 0/1 seconds throughout playback.
                    # Ignore implausible backwards jumps unless near the end (repeat).
                    if position>=predicted-1.5 or (predicted>=duration-3 and position<3):
                        self._anchor_position=position
                        self._anchor_time=now
                elif not chosen.get('music_playing'):
                    self._anchor_position=max(0.0,position if position is not None else self._anchor_position)
                    self._anchor_time=now
                if chosen.get('music_playing') and duration:
                    chosen['music_position']=min(duration,self._anchor_position+now-self._anchor_time)
                elif position is not None:
                    chosen['music_position']=self._anchor_position
                self.data=chosen
                self._sample_time=now
            await asyncio.sleep(1)
