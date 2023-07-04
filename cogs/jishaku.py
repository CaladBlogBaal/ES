from jishaku.cog import Jishaku

Jishaku.JISHAKU_RETAIN = True
Jishaku.JISHAKU_HIDE = True


async def setup(bot):
    await bot.add_cog(Jishaku(bot=bot))
