const express = require('express');
const cors = require('cors');
const { PrismaClient } = require('@prisma/client');
const Stripe = require('stripe');
const nodemailer = require('nodemailer');
require('dotenv').config();

const app = express();
const prisma = new PrismaClient();
const stripe = Stripe(process.env.STRIPE_SECRET_KEY);

// Middleware
app.use(cors());
app.use(express.json());

// Content Routes
app.get('/api/content/newsletter', async (req, res) => {
  try {
    const { week, tier } = req.query;
    const content = await contentService.getNewsletterContent(week, tier);
    res.json(content);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/content/research', async (req, res) => {
  try {
    const { category, timeframe } = req.query;
    const research = await contentService.getCuratedResearch(category, timeframe);
    res.json(research);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Subscription Routes
app.post('/api/subscribe', async (req, res) => {
  try {
    const { email, tier, paymentMethodId } = req.body;
    
    // Create Stripe customer
    const customer = await stripe.customers.create({
      email,
      payment_method: paymentMethodId,
    });

    // Create subscription
    const subscription = await stripe.subscriptions.create({
      customer: customer.id,
      items: [{
        price: getTierPriceId(tier),
      }],
    });

    // Save to database
    const user = await prisma.user.create({
      data: {
        email,
        stripeCustomerId: customer.id,
        subscriptionTier: tier,
        subscriptionId: subscription.id,
        status: 'active',
      },
    });

    // Send welcome email
    await emailService.sendWelcome(email, tier);

    res.json({ 
      success: true, 
      subscriptionId: subscription.id,
      clientSecret: subscription.latest_invoice.payment_intent.client_secret 
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// AI Content Generation Routes
app.post('/api/content/generate', async (req, res) => {
  try {
    const { type, researchPapers, style } = req.body;
    
    // Transform research papers using AI
    const transformedContent = await aiContentService.transformResearch({
      papers: researchPapers,
      style: 'professor-oh',
      contentType: type,
    });

    // Save generated content
    const content = await prisma.content.create({
      data: {
        type,
        title: transformedContent.title,
        body: transformedContent.body,
        researchSources: researchPapers,
        author: 'AI-Assisted (Prof. Oh)',
        status: 'published',
      },
    });

    res.json({ success: true, content });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// VOD Lecture Routes
app.get('/api/lectures', async (req, res) => {
  try {
    const { tier, category } = req.query;
    const lectures = await contentService.getLectures(tier, category);
    res.json(lectures);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Analytics Routes
app.get('/api/analytics/subscribers', async (req, res) => {
  try {
    const subscribers = await prisma.user.findMany({
      where: { status: 'active' },
      select: { subscriptionTier: true, createdAt: true },
    });

    const analytics = {
      total: subscribers.length,
      byTier: subscribers.reduce((acc, sub) => {
        acc[sub.subscriptionTier] = (acc[sub.subscriptionTier] || 0) + 1;
        return acc;
      }, {}),
      growth: calculateGrowth(subscribers),
    };

    res.json(analytics);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

function getTierPriceId(tier) {
  const prices = {
    'premium': process.env.STRIPE_PREMIUM_PRICE_ID,
    'vip': process.env.STRIPE_VIP_PRICE_ID,
  };
  return prices[tier];
}

function calculateGrowth(subscribers) {
  // Calculate month-over-month growth
  const thisMonth = subscribers.filter(s => {
    const created = new Date(s.createdAt);
    const now = new Date();
    return created.getMonth() === now.getMonth() && created.getFullYear() === now.getFullYear();
  }).length;

  const lastMonth = subscribers.filter(s => {
    const created = new Date(s.createdAt);
    const last = new Date();
    last.setMonth(last.getMonth() - 1);
    return created.getMonth() === last.getMonth() && created.getFullYear() === last.getFullYear();
  }).length;

  return {
    current: thisMonth,
    previous: lastMonth,
    growth: lastMonth > 0 ? ((thisMonth - lastMonth) / lastMonth) * 100 : 0,
  };
}

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`🚀 Longevity Platform API running on port ${PORT}`);
  console.log(`📚 Environment: ${process.env.NODE_ENV || 'development'}`);
  console.log(`💳 Stripe Mode: ${process.env.STRIPE_SECRET_KEY?.startsWith('sk_live') ? 'Live' : 'Test'}`);
});