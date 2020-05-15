import asyncio
import json
import KrogerCLI
from pyppeteer import launch


class KrogerAPI:
    browser_options = {
        'headless': True,
        'args': ['--blink-settings=imagesEnabled=false']  # Disable images for hopefully faster load-time
    }
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/81.0.4044.129 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
    }

    def __init__(self, cli: KrogerCLI):
        self.cli = cli

    def get_account_info(self):
        return asyncio.run(self._get_account_info())

    def clip_coupons(self):
        return asyncio.run(self._clip_coupons())

    async def _get_account_info(self):
        signed_in = await self.sign_in_routine()
        if not signed_in:
            await self.destroy()
            return None

        self.cli.console.print('Loading profile info..')
        await self.page.goto('https://www.' + self.cli.config['main']['domain'] + '/accountmanagement/api/profile')
        try:
            plain_text = await self.page.plainText()
            profile = json.loads(plain_text)
            user_id = profile['userId']
        except Exception:
            profile = None
        await self.destroy()

        return profile

    async def _clip_coupons(self):
        signed_in = await self.sign_in_routine(redirect_url='/cl/coupons/', contains=['Coupons Clipped'])
        if not signed_in:
            await self.destroy()
            return None

        js = """
            window.scrollTo(0, document.body.scrollHeight);
            for (let i = 0; i < 150; i++) {
                let el = document.getElementsByClassName('kds-Button--favorable')[i];
                if (el !== undefined) {
                    el.scrollIntoView();
                    el.click();
                }
            }
        """

        self.cli.console.print('[italic]Applying the coupons, please wait..[/italic]')
        await self.page.keyboard.press('Escape')
        for i in range(6):
            await self.page.evaluate(js)
            await self.page.keyboard.press('End')
            await self.page.waitFor(1000)
        await self.page.waitFor(3000)
        await self.destroy()
        self.cli.console.print('[bold]Coupons successfully clipped to your account! :thumbs_up:[/bold]')

    async def init(self):
        self.browser = await launch(self.browser_options)
        self.page = await self.browser.newPage()
        await self.page.setExtraHTTPHeaders(self.headers)
        await self.page.setViewport({'width': 700, 'height': 0})

    async def destroy(self):
        await self.browser.close()

    async def sign_in_routine(self, redirect_url='/account/update', contains=None):
        await self.init()
        self.cli.console.print('[italic]Signing in.. (please wait, it might take awhile)[/italic]')
        signed_in = await self.sign_in(redirect_url, contains)

        if not signed_in and self.browser_options['headless']:
            self.cli.console.print('[red]Sign in failed. Trying one more time..[/red]')
            self.browser_options['headless'] = False
            await self.destroy()
            await self.init()
            signed_in = await self.sign_in(redirect_url, contains)

        if not signed_in:
            self.cli.console.print('[bold red]Sign in failed. Please make sure the username/password is correct.'
                                   '[/bold red]')

        return signed_in

    async def sign_in(self, redirect_url, contains):
        timeout = 20000
        if not self.browser_options['headless']:
            timeout = 60000
        await self.page.goto('https://www.' + self.cli.config['main']['domain'] + '/signin?redirectUrl=' + redirect_url)
        await self.page.type('#SignIn-emailInput', self.cli.username)
        await self.page.type('#SignIn-passwordInput', self.cli.password)
        await self.page.keyboard.press('Enter')
        try:
            await self.page.waitForNavigation(timeout=timeout)
        except Exception:
            return False

        if contains is not None:
            html = await self.page.content()
            for item in contains:
                if item not in html:
                    return False

        return True