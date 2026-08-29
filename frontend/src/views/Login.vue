<template>
  <div class="login-container">
    <div class="login-card">
      <h1>Arrow Limousine</h1>
      <h2>Driver Portal</h2>

      <form v-if="step === 'credentials'" @submit.prevent="handleLogin">
        <p class="instructions">Your username is your last name followed by your first initial, for example <strong>smithj</strong>.</p>
        <div class="form-group">
          <label for="username">Username</label>
          <input id="username" v-model.trim="username" type="text" required autocomplete="username" :disabled="loading">
        </div>
        <div class="form-group">
          <label for="password">Password</label>
          <div class="password-row">
            <input
              id="password"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              required
              autocomplete="current-password"
              :disabled="loading"
            >
            <button class="password-toggle" type="button" :disabled="loading" @click="showPassword = !showPassword">
              {{ showPassword ? 'Hide Password' : 'Show Password' }}
            </button>
          </div>
        </div>
        <button type="submit" :disabled="loading">{{ loading ? 'Checking...' : 'Continue' }}</button>
      </form>

      <form v-else-if="step === 'change_password'" @submit.prevent="changePassword">
        <p class="instructions">Create your private password after confirming the security code sent to the mobile number in your employee file.</p>
        <div class="form-group">
          <label for="new-password">New password</label>
          <input id="new-password" v-model="newPassword" type="password" minlength="12" required autocomplete="new-password" :disabled="loading">
        </div>
        <div class="form-group">
          <label for="confirm-password">Confirm new password</label>
          <input id="confirm-password" v-model="confirmPassword" type="password" minlength="12" required autocomplete="new-password" :disabled="loading">
        </div>
        <p class="hint">Use at least 12 characters with upper-case, lower-case, and a number.</p>
        <button type="submit" :disabled="loading">{{ loading ? 'Saving...' : 'Save password' }}</button>
      </form>

      <form v-else-if="step === 'enroll_phone'" @submit.prevent="enrollPhone">
        <p class="instructions">Add your mobile number for two-step verification.</p>
        <div class="form-group">
          <label for="phone">Mobile phone</label>
          <input id="phone" v-model.trim="phone" type="tel" required autocomplete="tel" inputmode="tel" placeholder="403-555-0123" :disabled="loading">
        </div>
        <button type="submit" :disabled="loading">{{ loading ? 'Sending...' : 'Text verification code' }}</button>
      </form>

      <form v-else @submit.prevent="verifyCode">
        <p class="instructions">Enter the six-digit code sent to {{ maskedPhone }}.</p>
        <div class="form-group">
          <label for="verification-code">Verification code</label>
          <input
            id="verification-code"
            v-model.trim="code"
            type="text"
            required
            pattern="[0-9]{6}"
            maxlength="6"
            inputmode="numeric"
            autocomplete="one-time-code"
            :disabled="loading"
          >
        </div>
        <button type="submit" :disabled="loading">{{ loading ? 'Verifying...' : verificationButtonLabel }}</button>
      </form>

      <div v-if="error" class="error-message">{{ error }}</div>
      <button v-if="step === 'verify_activation' || step === 'verify_phone' || step === 'verify_mfa'" class="restart" type="button" :disabled="loading" @click="resendCode">
        Send another code
      </button>
      <button v-if="step === 'verify_phone'" class="restart" type="button" :disabled="loading" @click="step = 'enroll_phone'">
        Re-enter phone number
      </button>
      <button v-if="step !== 'credentials'" class="restart" type="button" :disabled="loading" @click="restart">
        Start over
      </button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Login',
  data() {
    return {
      step: 'credentials',
      username: '',
      password: '',
      showPassword: false,
      newPassword: '',
      confirmPassword: '',
      phone: '',
      code: '',
      challengeToken: '',
      maskedPhone: '',
      error: '',
      loading: false
    }
  },
  computed: {
    verificationButtonLabel() {
      if (this.step === 'verify_activation') return 'Verify and create private password'
      return 'Verify and open portal'
    }
  },
  methods: {
    async request(path, body) {
      const response = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.detail || 'Unable to continue')
      return data
    },
    applyNextStep(data) {
      this.step = data.next_step
      this.challengeToken = data.challenge_token || this.challengeToken
      this.maskedPhone = data.masked_phone || this.maskedPhone
      if (data.next_step === 'complete') {
        const user = data.user || {}
        localStorage.setItem('auth_token', data.access_token)
        localStorage.setItem('user', JSON.stringify(user))
        localStorage.setItem('user_role', user.role || 'driver')
        localStorage.setItem('user_permissions', JSON.stringify(user.permissions || {}))
        if (data.support_mode) {
          this.$router.push('/support')
        } else {
          this.$router.push('/')
        }
      }
    },
    async run(action) {
      this.error = ''
      this.loading = true
      try {
        this.applyNextStep(await action())
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    handleLogin() {
      return this.run(() => this.request('/auth/login', {
        username: this.username,
        password: this.password
      }))
    },
    changePassword() {
      if (this.newPassword !== this.confirmPassword) {
        this.error = 'The new passwords do not match'
        return
      }
      return this.run(() => this.request('/auth/change-password', {
        challenge_token: this.challengeToken,
        new_password: this.newPassword
      }))
    },
    enrollPhone() {
      return this.run(() => this.request('/auth/enroll-phone', {
        challenge_token: this.challengeToken,
        phone: this.phone
      }))
    },
    verifyCode() {
      return this.run(() => this.request('/auth/verify-code', {
        challenge_token: this.challengeToken,
        code: this.code
      }))
    },
    resendCode() {
      return this.run(() => this.request('/auth/resend-code', {
        challenge_token: this.challengeToken
      }))
    },
    restart() {
      this.step = 'credentials'
      this.password = ''
      this.showPassword = false
      this.newPassword = ''
      this.confirmPassword = ''
      this.phone = ''
      this.code = ''
      this.challengeToken = ''
      this.maskedPhone = ''
      this.error = ''
    }
  }
}
</script>

<style scoped>
.login-container { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 1rem; box-sizing: border-box; background: linear-gradient(135deg, #1d4ed8, #312e81); }
.login-card { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,.2); width: 100%; max-width: 420px; }
h1 { margin: 0 0 .35rem; color: #1e293b; font-size: 1.75rem; text-align: center; }
h2 { margin: 0 0 1.5rem; color: #64748b; font-size: 1.1rem; font-weight: normal; text-align: center; }
.instructions, .hint { color: #475569; line-height: 1.45; }
.hint { font-size: .85rem; }
.form-group { margin-bottom: 1rem; }
label { display: block; margin-bottom: .35rem; color: #1e293b; font-weight: 600; }
input { width: 100%; padding: .8rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 1rem; box-sizing: border-box; }
input:focus { outline: 2px solid #93c5fd; border-color: #2563eb; }
.password-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: .5rem; }
.password-row input { min-width: 0; }
.password-toggle { width: auto; white-space: nowrap; background: #e2e8f0; color: #1e293b; }
button { width: 100%; padding: .8rem; background: #2563eb; color: white; border: 0; border-radius: 6px; font-size: 1rem; font-weight: 600; cursor: pointer; }
button:disabled { opacity: .6; cursor: wait; }
.restart { margin-top: .75rem; background: transparent; color: #475569; }
.error-message { padding: .75rem; margin-top: 1rem; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; color: #991b1b; }
</style>
