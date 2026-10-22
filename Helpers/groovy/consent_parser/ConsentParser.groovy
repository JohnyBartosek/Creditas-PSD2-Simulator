package Helpers.groovy.consent_parser

import groovy.json.JsonOutput
import groovy.json.JsonSlurper

import java.time.Instant
import java.time.OffsetDateTime

/**
 * Picks the consent that belongs to a JWT and classifies each bank profile
 * as owner or disponent.
 *
 * A consent matches when all of the following hold:
 * - jwt.sub == consent.ownerId
 * - jwt.azp == consent.oauth2ClientId
 * - jwt scope families {aisp, pisp} equal the families of consent.scopes
 * - jwt.bank_profile_ids and consent.disponentIds contain the same ids
 * - the consent is active at jwt.iat (not recalled, validFrom <= iat <= validTo)
 *
 * Scope families: "aisp" / "pisp" in any order on the token;
 * AISP.* maps to aisp, PISP.PaymentInitiation maps to pisp.
 */
class ConsentParser {

    private static final Set<String> AISP_SCOPES = [
            'AISP.AccountList',
            'AISP.Balance',
            'AISP.TransactionList',
    ] as Set

    private static final Set<String> PISP_SCOPES = [
            'PISP.PaymentInitiation',
    ] as Set

    static Map parse(Map jwt, List consents) {
        def consent = selectConsent(jwt, consents)
        if (consent == null) {
            return [ProfileRelations: []]
        }
        def ownerId = idOf(jwt?.sub)
        def consentOwnerId = idOf(consent.ownerId)
        def rows = (jwt?.bank_profile_ids ?: []).collect { profile ->
            def profileId = idOf(profile)
            def role = (profileId == ownerId && profileId == consentOwnerId) ? 'owner' : 'disponent'
            [profileOwnerId: profileId, userProfileRole: role]
        }
        def relations = rows.findAll { it.userProfileRole == 'owner' } + rows.findAll { it.userProfileRole == 'disponent' }
        return [ProfileRelations: relations]
    }

    static Map parse(String jwtJson, String consentsJson) {
        def slurper = new JsonSlurper()
        parse(slurper.parseText(jwtJson) as Map, slurper.parseText(consentsJson) as List)
    }

    private static Map selectConsent(Map jwt, List consents) {
        if (!jwt || !consents) {
            return null
        }
        def at = referenceTime(jwt)
        def active = consents.findAll { consent -> matches(jwt, consent) && activeAt(consent, at) }
        if (!active) {
            return null
        }
        return active.max { a, b ->
            def byFrom = compareInstant(a?.validFrom, b?.validFrom)
            byFrom != 0 ? byFrom : (asLong(a?.consentId) <=> asLong(b?.consentId))
        }
    }

    private static boolean matches(Map jwt, Map consent) {
        if (consent == null) {
            return false
        }
        if (!idOf(jwt?.sub) || idOf(jwt.sub) != idOf(consent.ownerId)) {
            return false
        }
        if (!jwt?.azp || jwt.azp.toString() != consent.oauth2ClientId?.toString()) {
            return false
        }
        def jwtFamilies = scopeFamilies(jwt)
        def consentFamilies = consentScopeFamilies(consent.scopes)
        if (!jwtFamilies || consentFamilies == null || jwtFamilies != consentFamilies) {
            return false
        }
        def profiles = idSet(jwt.bank_profile_ids)
        def disponents = idSet(consent.disponentIds)
        return profiles && profiles == disponents
    }

    private static boolean activeAt(Map consent, Instant at) {
        if (consent?.recalledAt) {
            return false
        }
        def from = instantOf(consent?.validFrom)
        def to = instantOf(consent?.validTo)
        if (from != null && at.isBefore(from)) {
            return false
        }
        if (to != null && at.isAfter(to)) {
            return false
        }
        return true
    }

    private static Set<String> scopeFamilies(Map jwt) {
        def raw = jwt?.scope != null ? jwt.scope : jwt?.scopes
        def tokens = []
        if (raw instanceof Collection) {
            tokens.addAll(raw)
        } else if (raw != null) {
            tokens.addAll(raw.toString().trim().split(/\s+/).findAll { it })
        }
        tokens.collect { it.toString().trim().toLowerCase() }
                .findAll { it in ['aisp', 'pisp'] } as Set
    }

    /**
     * @return family set, or null when a consent scope is outside aisp/pisp
     */
    private static Set<String> consentScopeFamilies(scopes) {
        def families = [] as Set
        for (scope in scopes ?: []) {
            def name = scope?.toString()
            if (name in AISP_SCOPES) {
                families << 'aisp'
            } else if (name in PISP_SCOPES) {
                families << 'pisp'
            } else {
                return null
            }
        }
        return families
    }

    private static Instant referenceTime(Map jwt) {
        def epoch = jwt?.iat != null ? jwt.iat : jwt?.nbf
        if (epoch instanceof Number) {
            return Instant.ofEpochSecond((epoch as Number).longValue())
        }
        return Instant.now()
    }

    private static Set<String> idSet(value) {
        if (!(value instanceof Collection)) {
            return [] as Set
        }
        value.collect { idOf(it) }.findAll { it } as Set
    }

    private static String idOf(value) {
        if (value == null) {
            return ''
        }
        if (value instanceof Number) {
            return (value as BigDecimal).stripTrailingZeros().toPlainString()
        }
        return value.toString().trim()
    }

    private static Instant instantOf(value) {
        if (value == null) {
            return null
        }
        if (value instanceof Number) {
            return Instant.ofEpochSecond((value as Number).longValue())
        }
        def text = value.toString().trim()
        if (!text) {
            return null
        }
        try {
            return Instant.parse(text)
        } catch (ignored) {
            return OffsetDateTime.parse(text).toInstant()
        }
    }

    private static int compareInstant(left, right) {
        def a = instantOf(left) ?: Instant.EPOCH
        def b = instantOf(right) ?: Instant.EPOCH
        return a <=> b
    }

    private static long asLong(value) {
        return value instanceof Number ? (value as Number).longValue() : 0L
    }

    static void main(String[] args) {
        if (args == null || args.length < 2) {
            return
        }
        def slurper = new JsonSlurper()
        def jwt = slurper.parse(new File(args[0]))
        def consents = slurper.parse(new File(args[1]))
        println JsonOutput.prettyPrint(JsonOutput.toJson(parse(jwt as Map, consents as List)))
    }
}
