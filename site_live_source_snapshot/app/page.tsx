import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "NetzaraBot Live",
  description:
    "Mobile-first Deriv live auto-trading app with subscription, referrals, and guarded real-money execution.",
};

const partnerSignupUrl =
  "https://deriv.partners/rx?sidc=D316D854-232F-4E4D-A83B-D91E7390C283&utm_campaign=dynamicworks&utm_medium=affiliate&utm_source=CU38751";

export default function Home() {
  return (
    <main>
      <div className="topbar">
        <div className="logo">
        <div className="logoMark">NB</div>
        <div>
            <div>NetzaraBot Live</div>
            <small>Mobile Deriv live auto-trading app</small>
        </div>
        </div>
        <div className="pill">Live trading mode</div>
      </div>

      <section className="hero" id="home">
        <div className="heroText">
          <p className="eyebrow">NetzaraBot live execution</p>
          <h1>Hands-free Deriv live auto-trading for subscribers.</h1>
          <p>
            Users pay $50/month, connect Deriv, choose risk limits, and let the
            approved bot trade automatically 24/7. Profit-share tracking is
            built around 20% of net profits after profitable cycles.
          </p>
          <div className="actions">
            <a className="button secondary" href={partnerSignupUrl}>
              Create Deriv account
            </a>
            <a className="button ghost" href="#connect">
              Connect existing Deriv
            </a>
            <a className="button ghost" href="#autotrade">
              Auto-trade setup
            </a>
          </div>
        </div>
      </section>

      <section className="grid cols4">
        <div className="card stat">
          <strong>$50</strong>
          <small>Monthly subscription</small>
        </div>
        <div className="card stat">
          <strong>20%</strong>
          <small>Profit-share target</small>
        </div>
        <div className="card stat">
          <strong>24/7</strong>
          <small>Server-run trading</small>
        </div>
        <div className="card stat">
          <strong>Deriv</strong>
          <small>Required account/API</small>
        </div>
      </section>

      <section className="section grid cols2">
        <div className="card">
          <h2>Customer Path</h2>
          <div className="steps">
            <div className="step">
              <h3>Subscribe</h3>
              <p>User pays $50/month before auto-trading access unlocks.</p>
            </div>
            <div className="step">
              <h3>Create or connect Deriv</h3>
              <p>
                New users open Deriv through the embedded partner path.
                Existing users connect by OAuth or API token.
              </p>
            </div>
            <div className="step">
              <h3>Choose risk limits</h3>
              <p>
                User sets max daily loss, max open trades, allowed markets, and
                emergency stop rules.
              </p>
            </div>
            <div className="step">
              <h3>Run auto-trading</h3>
              <p>
                The cloud bot trades only approved strategies and logs
                profit-share calculations.
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <h2>Live Trading Status</h2>
          <div className="status locked">
            <span>✓</span>
            <div>
              Live execution backend is active
              <p>
                The website supports Deriv/payment backend routes for real-money
                test trading. Orders still require a connected Deriv token,
                account ID, explicit consent, and risk limits before submission.
              </p>
            </div>
          </div>
          <div className="status review">
            <span>?</span>
            <div>
              20% profit-share needs legal setup
              <p>
                The app can track the ledger now. Collecting it should wait for
                terms, risk disclosure, country rules, and correct net-profit
                accounting.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="section card" id="connect">
        <h2>Deriv Account Connection</h2>
        <div className="grid cols2">
          <div className="innerCard">
            <h3>Option 1: I do not have Deriv</h3>
            <p>
              Tap the button below. The partner link is embedded, so users do
              not see or copy your affiliate URL.
            </p>
            <div className="actions">
              <a className="button" href={partnerSignupUrl}>
                Create Deriv account
              </a>
            </div>
          </div>
          <div className="innerCard">
            <h3>Option 2: I already have Deriv</h3>
            <p>
              Connect securely using Deriv OAuth where possible. For early
              manual setup, create a Deriv API token and paste it into the app.
            </p>
            <div className="actions">
              <a className="button ghost" href="#tokenGuide">
                How to connect API
              </a>
            </div>
          </div>
        </div>
      </section>

      <section className="section grid cols3" id="plans">
        <div className="card">
          <h2>Subscription</h2>
          <div className="price">
            $50 <small>/ month</small>
          </div>
          <ul>
            <li>Auto-trading dashboard</li>
            <li>Deriv connection required</li>
            <li>Telegram/mobile alerts</li>
            <li>Risk controls included</li>
            <li>Founder/admin account can be marked free</li>
          </ul>
          <div className="actions">
            <a className="button" href="/api/payments/checkout">
              Subscribe
            </a>
          </div>
        </div>
        <div className="card">
          <h2>Profit Share</h2>
          <div className="price">
            20% <small>of net profit</small>
          </div>
          <ul>
            <li>Calculated after closed trades</li>
            <li>Losses carried before fee</li>
            <li>No fee on losing periods</li>
            <li>Requires legal/compliance approval</li>
          </ul>
        </div>
        <div className="card">
          <h2>Referral</h2>
          <div className="price">
            5% <small>registration fee</small>
          </div>
          <ul>
            <li>Referral codes for users</li>
            <li>Separate from Deriv partner commission</li>
            <li>Track paid and pending referrals</li>
            <li>Admin approval before payout</li>
          </ul>
          <div className="copybox">Example code: TA-4821</div>
        </div>
      </section>

      <section className="section card" id="autotrade">
        <h2>Auto-Trade Setup</h2>
        <div className="setupGrid">
          <div>
            <label>Trading mode</label>
            <div className="inputLike">Real-money live test</div>
          </div>
          <div>
            <label>Allowed strategy</label>
            <div className="inputLike">One approved strategy at a time first</div>
          </div>
          <div>
            <label>Max daily loss</label>
            <div className="inputLike">2% of balance</div>
          </div>
          <div>
            <label>Max open trades</label>
            <div className="inputLike">1</div>
          </div>
          <div>
            <label>Take profit</label>
            <div className="inputLike">Fixed target or bot-approved take-profit level</div>
          </div>
          <div>
            <label>Profit-share cycle</label>
            <div className="inputLike">Weekly or monthly net profit</div>
          </div>
          <div>
            <label>Emergency stop</label>
            <div className="inputLike">Stop after one loss or execution error</div>
          </div>
        </div>
        <div className="status locked">
          <span>!</span>
          <div>
            Real order backend: installed
            <p>
              The website now has backend routes for payment checkout, Deriv
              OAuth, and Deriv trade execution. Live trading requires your
              Deriv/payment environment keys, connected user token, and explicit
              account consent before an order can be sent.
            </p>
          </div>
        </div>
        <div className="actions">
          <a className="button ghost" href="/api/system/readiness">
            Check backend readiness
          </a>
          <a className="button ghost" href="/api/deriv/oauth/start">
            Connect Deriv OAuth
          </a>
        </div>
      </section>

      <section className="section card">
        <h2>Founder Token Test</h2>
        <p>
          If you already created a Deriv API token, test it privately from
          your terminal against `/api/deriv/token/check`. The test checks account
          access and permissions only; it does not place trades.
        </p>
        <div className="copybox">Token needs Read and Trade permissions for the account you want to test.</div>
      </section>

      <section className="section card" id="tokenGuide">
        <h2>How To Register Deriv API</h2>
        <div className="grid cols2">
          <div className="innerCard">
            <h3>For You, The App Owner</h3>
            <ol>
              <li>Log in to your Deriv account.</li>
              <li>Open the Deriv developers/API area.</li>
              <li>Create a new app.</li>
              <li>Name it NetzaraBot Live.</li>
              <li>Add this redirect URL: https://www.netzarabot.com/api/deriv/oauth/callback</li>
              <li>Enable trading/account scopes required by Deriv.</li>
              <li>Copy the App ID or Client ID and add it to this website backend.</li>
            </ol>
          </div>
          <div className="innerCard">
            <h3>For A Customer</h3>
            <ol>
              <li>Create a Deriv account from the app button, or log in if already registered.</li>
              <li>Choose Connect Deriv OAuth inside the app.</li>
              <li>Approve the requested permissions.</li>
              <li>Set risk controls, including stake, stop loss, take profit, max daily loss, and max open trades.</li>
              <li>Start live mode only after selecting a small test stake and risk limit.</li>
            </ol>
          </div>
        </div>
      </section>

      <section className="section card">
        <h2>Manual API Token Option</h2>
        <ol>
          <li>Log in to Deriv.</li>
          <li>Open Dashboard or account settings.</li>
          <li>Go to API tokens.</li>
          <li>Create a new token.</li>
          <li>Select only the required scopes. Avoid Admin permission.</li>
          <li>Copy the token immediately and paste it into the app.</li>
        </ol>
        <p className="fineprint">
          OAuth should be the preferred production path for mobile/web users.
          Manual API token entry is mainly for early testing.
        </p>
      </section>
    </main>
  );
}
