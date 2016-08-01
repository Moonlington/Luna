import discord
from discord.ext import commands
import youtube_dl
import functools


def setup(bot):
    bot.add_cog(Music(bot))


class VoiceEntry:

    def __init__(self, bot, message, url):
        self.requester = message.author
        self.bot = bot
        self.channel = message.channel
        self.url = url

    async def getInfo(self):
        opts = {
        "format": 'webm[abr>0]/bestaudio/best',
        "ignoreerrors": True,
        "default_search": "auto",
        "source_address": "0.0.0.0",
        'quiet': True}
        ydl = youtube_dl.YoutubeDL(opts)
        func = functools.partial(ydl.extract_info, self.url, download=False)
        info = await self.bot.loop.run_in_executor(None, func)
        if "entries" in info:
            info = info['entries'][0]
        self.info = info
        self.download_url = info.get('url')
        self.views = info.get('view_count')
        self.is_live = bool(info.get('is_live'))
        self.likes = info.get('like_count')
        self.dislikes = info.get('dislike_count')
        self.duration = info.get('duration')
        self.uploader = info.get('uploader')

        is_twitch = 'twitch' in self.url
        if is_twitch:
            self.title = info.get('description')
            self.description = None
        else:
            self.title = info.get('title')
            self.description = info.get('description')

        date = info.get('upload_date')
        if date:
            try:
                date = datetime.datetime.strptime(date, '%Y%M%d').date()
            except ValueError:
                date = None

        self.upload_date = date

    def __str__(self):
        fmt = '**{0.title}** uploaded by **{0.uploader}** and requested by **{1.display_name}**'
        if self.duration:
            fmt += ' `[length: {0[0]}m {0[1]}s]`'.format(divmod(self.duration, 60))
        return fmt.format(self, self.requester)

    def __repr__(self):
        return '<{0.title}, {0.requester.display_name}>'.format(self)


class VoiceState:

    def __init__(self, _bot):
        self.current = None
        self.voice = None
        self.currenttime = None
        self.empty = None
        self.currentplayer = None
        self.bot = _bot
        self.play_next_song = asyncio.Event()
        self.songs = asyncio.Queue()
        self.skip_votes = set()  # a set of user_ids that voted
        self.audio_player = self.bot.loop.create_task(self.audio_player_task())

    def is_playing(self):
        if self.voice is None or self.currentplayer is None:
            return False

        player = self.currentplayer
        return not player.is_done()

    @property
    def player(self):
        return self.currentplayer

    def skip(self):
        self.skip_votes.clear()
        if self.is_playing():
            self.player.stop()

    def toggle_next(self):
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    def create_player(self, entry):
        player = self.voice.create_ffmpeg_player(entry.download_url, after=self.toggle_next)
        player.volume = 0.55
        return player

    async def audio_player_task(self):
        while True:
            self.play_next_song.clear()
            self.empty = self.songs.empty()
            self.current = await self.songs.get()
            self.currentplayer = self.create_player(self.current)
            if not self.empty:
                await self.bot.send_message(self.current.channel, 'Now playing ' + str(self.current))
            self.currenttime = datetime.datetime.now()
            self.currentplayer.start()
            await self.play_next_song.wait()


class Music:

    def __init__(self, _bot):
        self.bot = _bot
        self.voice_states = {}

    def get_voice_state(self, server):
        state = self.voice_states.get(server.id)
        if state is None:
            state = VoiceState(self.bot)
            self.voice_states[server.id] = state

        return state

    async def create_voice_bot(self, channel):
        voice = await self.bot.join_voice_channel(channel)
        state = self.get_voice_state(channel.server)
        state.voice = voice

    def __unload(self):
        for state in self.voice_states.values():
            try:
                state.audio_player.cancel()
                if state.voice:
                    self.bot.loop.create_task(state.voice.disconnect())
            except:
                pass

    @commands.group(
        pass_context=True,
        description='Various music/voice channel commands for Luna.',
        aliases=['lm'])
    async def music(self, ctx):
        """Music commands for Luna."""
        if ctx.invoked_subcommand is None:
            await self.bot.say('Use `&help music` or `&help lm` to see the subcommands.')


    @music.command(no_pm=True)
    async def join(self, *, channel: discord.Channel):
        """Joins a voice channel."""
        try:
            await self.bot.create_voice_bot(channel)
        except discord.InvalidArgument:
            await self.bot.say('This is not a voice channel...')
        except discord.ClientException:
            await self.bot.say('Already in a voice channel...')
        else:
            await self.bot.say('Ready to play audio in ' + channel.name)


    @music.command(pass_context=True, no_pm=True)
    async def summon(self, ctx):
        """Summons the bot to join your voice channel."""
        summoned_channel = ctx.message.author.voice_channel
        if summoned_channel is None:
            await self.bot.say('You are not in a voice channel.')
            return False

        state = bot.get_voice_state(ctx.message.server)
        if state.voice is None:
            state.voice = await self.bot.join_voice_channel(summoned_channel)
        else:
            await state.voice.move_to(summoned_channel)

        return True


    @music.command(pass_context=True, no_pm=True)
    async def play(self, ctx, *, song: str):
        """Plays a song.
        If there is a song currently in the queue, then it is
        queued until the next song is done playing.
        This command automatically searches as well from YouTube.
        The list of supported sites can be found here:
        https://rg3.github.io/youtube-dl/supportedsites.html
        """
        state = bot.get_voice_state(ctx.message.server)
        opts = {
            "format": 'webm[abr>0]/bestaudio/best',
            "ignoreerrors": True,
            "default_search": "ytsearch",
            "source_address": "0.0.0.0",
            'quiet': True}

        ytdl = youtube_dl.YoutubeDL({
            "format": 'best',
            "ignoreerrors": True,
            "default_search": "ytsearch",
            "source_address": "0.0.0.0"})
        if state.voice is None:
            success = await ctx.invoke(summon)
            if not success:
                return
        shuffle = True if ' +shuffle' in song else False
        if shuffle:
            song.replace(' +shuffle', '')
        if 'playlist?list=' in song:
            await self.bot.say('Playlist detected, enqueuing all items...')
            info = ytdl.extract_info(song, download=False, process=False)
            songlist = []
            for e in info['entries']:
                if e:
                    if 'youtube' in info['extractor']:
                        songlist.append('https://www.youtube.com/watch?v={}'.format(e['id']))
            firstsong = None
            weeee = True if not state.is_playing() else False
            if shuffle:
                random.shuffle(songlist)
            for video in songlist:
                entry = VoiceEntry(bot, ctx.message, video)
                await entry.getInfo()
                if songlist.index(video) == 0:
                    firstsong = entry
                await state.songs.put(entry)
            if weeee:
                await self.bot.say('Successfully enqueued **{}** entries and started playing {}'.format(len(songlist), firstsong))
            else:
                await self.bot.say('Successfully enqueued **{}** entries!'.format(len(songlist)))
        else:
            entry = VoiceEntry(bot, ctx.message, song)
            await entry.getInfo()
            if not state.is_playing():
                await self.bot.say('Enqueued and now playing ' + str(entry))
            else:
                await self.bot.say('Enqueued ' + str(entry))
            await state.songs.put(entry)


    @music.command(pass_context=True, no_pm=True)
    async def volume(self, ctx, value: int):
        """Sets the volume of the currently playing song."""
        state = bot.get_voice_state(ctx.message.server)
        if state.is_playing():
            player = state.player
            player.volume = value / 100
            await self.bot.say('Set the volume to {:.0%}'.format(player.volume))


    @music.command(pass_context=True, no_pm=True)
    async def pause(self, ctx):
        """Pauses the currently played song."""
        state = bot.get_voice_state(ctx.message.server)
        if state.is_playing():
            player = state.player
            player.pause()


    @music.command(pass_context=True, no_pm=True)
    async def resume(slef, ctx):
        """Resumes the currently played song."""
        state = bot.get_voice_state(ctx.message.server)
        if state.is_playing():
            player = state.player
            player.resume()


    @music.command(pass_context=True, no_pm=True)
    async def stop(self, ctx):
        """Stops playing audio and leaves the voice channel.
        This also clears the queue.
        """
        server = ctx.message.server
        state = bot.get_voice_state(server)

        if state.is_playing():
            player = state.player
            player.stop()

        try:
            state.audio_player.cancel()
            del bot.voice_states[server.id]
            await state.voice.disconnect()
        except:
            pass


    @music.command(pass_context=True, no_pm=True)
    async def skip(self, ctx):
        """Vote to skip a song. The song requester can automatically skip.
        3 skip votes are needed for the song to be skipped.
        """
        state = bot.get_voice_state(ctx.message.server)
        if not state.is_playing():
            await self.bot.say('Not playing any music right now...')
            return

        voter = ctx.message.author
        if voter == state.current.requester:
            await self.bot.say('Requester requested skipping song...')
            state.skip()
        elif voter.id not in state.skip_votes:
            state.skip_votes.add(voter.id)
            total_votes = len(state.skip_votes)
            if total_votes >= 3:
                await self.bot.say('Skip vote passed, skipping song...')
                state.skip()
            else:
                await self.bot.say('Skip vote added, currently at [{}/3]'.format(total_votes))
        else:
            await self.bot.say('You have already voted to skip this song.')


    @music.command(pass_context=True, no_pm=True)
    async def playing(self, ctx):
        """Shows info about the currently played song."""
        state = bot.get_voice_state(ctx.message.server)
        if state.current is None:
            await self.bot.say('Not playing anything.')
        else:
            skip_count = len(state.skip_votes)
            t1 = state.currenttime
            t2 = datetime.datetime.now()
            duration = (t2 - t1).total_seconds()
            await self.bot.say(
                'Now playing {0} [skips: {1}/3] [{2[0]}m {2[1]}s/{3[0]}m {3[1]}s]'.format(state.current, skip_count, divmod(math.floor(duration), 60), divmod(state.current.player.duration, 60)))


    @music.command(name='list', pass_context=True, no_pm=True)
    async def _list(self, ctx):
        """Shows the queue for your server."""
        state = bot.get_voice_state(ctx.message.server)
        entries = [x for x in state.songs._queue]
        if len(entries) == 0:
            await self.bot.say("There are currently no songs in the queue!")
        else:
            counter = 1
            totalduration = 0
            send = '__Found queue of **{1}** for **{0}**__\n'.format(
                ctx.message.server.name, len(entries))
            for entry in entries[:10]:
                requester = entry.requester
                player = entry
                send += '[{0[0]}m {0[1]}s] {1}. **{2}** requested by **{3}**\n'.format(
                    divmod(player.duration, 60), counter, player.title, requester.display_name)
                counter += 1
            for entry in entries:
                player = entry
                totalduration += player.duration
            send += 'Total duration: `[{0}]`'.format(
                datetime.timedelta(seconds=totalduration))
            await self.bot.say(send)