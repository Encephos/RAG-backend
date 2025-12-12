'use server'

import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

export async function login(prevState: any, formData: FormData) {
    const password = formData.get('password') as string
    const correctPassword = process.env.AUTH_PASSWORD

    if (!correctPassword) {
        console.error("AUTH_PASSWORD is not set in environment variables!")
        return { error: 'Server misconfiguration: Authentication not set up.' }
    }

    if (password === correctPassword) {
        const cookieStore = await cookies()
        cookieStore.set('auth_token', 'authenticated', {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            maxAge: 60 * 60 * 24 * 7, // 1 week
            path: '/',
        })
        redirect('/')
    }

    return { error: 'Wrong password' }
}
