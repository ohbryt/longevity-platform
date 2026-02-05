#!/bin/bash

echo "🚀 Launching Longevity Platform Development Environment"
echo "================================================"

# Load Node.js environment
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

cd /Users/chang-myungoh/longevity-platform

echo "📦 Installing dependencies..."
npm install

echo "🗄️ Setting up database..."
cd backend
npm install @prisma/client
npx prisma generate
echo "✅ Database schema generated"

echo "🤖 Building AI content service..."
cd ../ai-content
npm install
echo "✅ AI content service ready"

echo "🎨 Building frontend..."
cd ../frontend
npm install
echo "✅ Frontend dependencies installed"

echo "🔧 Testing AI content generation..."
cd ../ai-content
node -e "
const { AIContentService } = require('./index.js');

async function testAI() {
  try {
    console.log('🧪 Testing AI Content Generation...');
    
    const service = new AIContentService();
    const testPapers = [
      {
        title: 'Senolytics Trial Results Show Promise',
        abstract: 'Recent clinical trials of senolytic drugs show significant reduction in senescent cell markers...',
        keyFindings: '50% reduction in p16INK4a levels, improved metabolic markers',
        journal: 'Nature Aging',
        publicationDate: new Date('2024-01-15')
      }
    ];

    const result = await service.transformResearch({
      papers: testPapers,
      style: 'professor-oh',
      contentType: 'newsletter'
    });

    console.log('✅ Test Content Generated:');
    console.log('Title:', result.title);
    console.log('Length:', result.body.length, 'characters');
    console.log('Preview:', result.body.substring(0, 200) + '...');
    
    return true;
  } catch (error) {
    console.error('❌ AI Test Failed:', error.message);
    return false;
  }
}

testAI().then(success => {
  if (success) {
    console.log('🎉 AI Content Pipeline Working!');
  } else {
    console.log('❌ AI Content Pipeline Failed');
  }
});
"
echo "✅ AI content generation test completed"

echo "🌐 Starting development servers..."
cd ../backend
export PORT=3001
export DATABASE_URL="postgresql://localhost:5432/longevity_dev"
export OPENAI_API_KEY="test-key"
export ANTHROPIC_API_KEY="test-key"
export STRIPE_SECRET_KEY="sk_test_key"
export NEXT_PUBLIC_APP_URL="http://localhost:3000"

# Start backend in background
node src/index.js &
BACKEND_PID=$!

cd ../frontend
export NEXT_PUBLIC_APP_URL="http://localhost:3000"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "🚀 Longevity Platform Development Environment Ready!"
echo "================================================"
echo "📊 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:3001"
echo "📚 Database: PostgreSQL on localhost:5432"
echo ""
echo "🎯 Next Steps:"
echo "1. Test AI content generation at http://localhost:3001/api/content/generate"
echo "2. Set up PostgreSQL database and run migrations"
echo "3. Configure Stripe keys for payment testing"
echo "4. Test user subscription flow"
echo "5. Deploy to production when ready"
echo ""
echo "💡 Use 'ultrawork' keyword with OpenCode for advanced development!"
echo ""

# Function to cleanup on exit
cleanup() {
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "✅ Servers stopped"
}

trap cleanup EXIT

# Wait for user input to stop
echo "Press Ctrl+C to stop servers..."
wait