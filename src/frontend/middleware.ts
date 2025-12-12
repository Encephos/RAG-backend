import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
    // Check for auth cookie
    const authToken = request.cookies.get('auth_token')
    const isAuthenticated = !!authToken

    // Define paths that are always accessible
    const isPublicPath =
        request.nextUrl.pathname === '/login' ||
        request.nextUrl.pathname.startsWith('/_next') ||
        request.nextUrl.pathname.startsWith('/api') ||
        request.nextUrl.pathname.startsWith('/static') ||
        request.nextUrl.pathname.includes('.') // Files (images, etc)

    if (!isAuthenticated && !isPublicPath) {
        return NextResponse.redirect(new URL('/login', request.url))
    }

    if (isAuthenticated && request.nextUrl.pathname === '/login') {
        return NextResponse.redirect(new URL('/', request.url))
    }

    return NextResponse.next()
}

export const config = {
    matcher: [
        /*
         * Match all request paths except for the ones starting with:
         * - api (API routes)
         * - _next/static (static files)
         * - _next/image (image optimization files)
         * - favicon.ico (favicon file)
         */
        '/((?!api|_next/static|_next/image|favicon.ico).*)',
    ],
}
