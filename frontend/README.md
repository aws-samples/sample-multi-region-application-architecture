# AirportHub OS - Frontend

React-based dashboard for AirportHub OS — gives airport executives a real-time view of flights, crew assignments, and airport operations.

## Technology Stack

- **React 19** with TypeScript
- **Vite 7** - Build tool
- **Tailwind CSS 4** - Utility-first styling
- **React Router v7** - Client-side routing
- **Amazon Cognito** - Authentication (JWT-based)
- **Context API** - State management

## Project Structure

```
frontend/
├── src/
│   ├── components/           # Reusable UI components
│   │   ├── Header.tsx        #   Navigation bar with region badge
│   │   ├── FlightBoard.tsx   #   Live flight board with filters
│   │   ├── FlightFilters.tsx #   Airport/status/time window filters
│   │   ├── AirportTable.tsx  #   Searchable airport table
│   │   ├── StatsCard.tsx     #   Reusable stat display card
│   │   └── ProtectedRoute.tsx#   Auth guard for protected pages
│   ├── pages/                # Page components
│   │   ├── Home.tsx          #   Dashboard with stats and navigation
│   │   ├── Crew.tsx          #   Crew assignments, pilots, flight attendants
│   │   ├── AirportList.tsx   #   Airport directory
│   │   ├── AddAirport.tsx    #   Add new airport form
│   │   ├── Tech.tsx          #   Technical info and region status
│   │   └── auth/             #   Authentication pages
│   │       ├── Login.tsx
│   │       ├── SignUp.tsx
│   │       ├── VerifyEmail.tsx
│   │       ├── ForgotPassword.tsx
│   │       ├── ResetPassword.tsx
│   │       └── MfaSetup.tsx
│   ├── context/
│   │   ├── AuthContext.tsx    #   Cognito auth state
│   │   └── AppContext.tsx     #   App-wide state (region, loading)
│   ├── utils/
│   │   ├── api.ts            #   API clients (airports, flights, crew)
│   │   └── cognito.ts        #   Cognito SDK wrapper
│   ├── App.tsx               #   Routes and layout
│   └── main.tsx              #   Entry point
├── dist/                     # Pre-built static assets (served by Flask)
├── package.json
├── vite.config.ts
└── tailwind.config.js
```

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Home | Dashboard with quick stats, region status, navigation |
| `/airports` | AirportList | Searchable airport directory |
| `/add` | AddAirport | Form to add a new airport |
| `/tech` | Tech | Technical details — region, DocumentDB, ECS status |
| `/crew` | Crew | Crew assignments, pilots, flight attendants, aircraft |
| `/login` | Login | Cognito authentication |
| `/signup` | SignUp | User registration |
| `/mfa-setup` | MfaSetup | TOTP MFA enrollment |

## API Integration

The frontend talks to three backend services, all authenticated with Cognito JWTs:

```typescript
// Airport API (Flask backend via ALB)
api.getAirports(limit)        // GET /api/airports
api.getAirport('ATL')         // GET /api/airports/ATL
api.createAirport(data)       // POST /api/airports
api.getStats()                // GET /api/stats

// Flights API (Lambda via API Gateway)
flightsApi.getFlights(filters) // GET /flights?airport=&status=&window=
flightsApi.getFlightStats()    // GET /flights/stats
flightsApi.refreshFlights()    // POST /flights/refresh

// Crew API (Lambda via ALB)
crewApi.getPilots(filters)          // GET /crew/pilots
crewApi.getFlightAttendants(filters)// GET /crew/flight-attendants
crewApi.getAircraft()               // GET /crew/aircraft
crewApi.getAssignments(filters)     // GET /crew/assignments
```

## Authentication

All app routes are protected by `ProtectedRoute` — unauthenticated users are redirected to `/login`. Auth is handled via Amazon Cognito with `amazon-cognito-identity-js`. The `authFetch` wrapper automatically attaches JWT tokens and handles 401 (session expired) by redirecting to login.

## Styling

Dark theme with custom Tailwind colors:
- `surface` — dark navy backgrounds (`#0f172a`, `#1e293b`)
- `accent` — sky blue highlights (`#38bdf8`)
- `status` — green/yellow/red/orange for operational status indicators

## Development

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
npm run build      # Output: dist/
```

Note: The `dist/` folder is pre-built and committed — CodeBuild uses it directly when building the container image. You only need to run `npm run build` if you modify frontend source.

## Deployment

The frontend is deployed as part of the ECS container. CodeBuild builds the Docker image (which includes the pre-built `dist/` assets served by Flask) and pushes to ECR. No local container tooling is required.

```bash
# Full-stack deploy from project root
python3 deploy.py --profile <profile>
```

## License

MIT
